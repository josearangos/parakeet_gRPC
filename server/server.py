"""gRPC server: validates the stream, drives the ASR engine, maps failures to status codes."""
import logging
import signal
import threading
import time
from concurrent import futures

import grpc
import numpy as np

import generated  # noqa: F401  (makes speech_pb2 importable)
import speech_pb2
import speech_pb2_grpc

from server.asr import EngineBusy
from server.config import ServerSettings, load_settings

log = logging.getLogger("asr.server")

SAMPLE_WIDTH = 2  # PCM_S16LE


class _Reject(Exception):
    def __init__(self, code: grpc.StatusCode, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _validate_config(cfg, settings: ServerSettings) -> None:
    if cfg.encoding != speech_pb2.PCM_S16LE:
        raise _Reject(grpc.StatusCode.INVALID_ARGUMENT, "unsupported encoding; expected PCM_S16LE")
    if cfg.sample_rate_hz != settings.sample_rate:
        raise _Reject(grpc.StatusCode.INVALID_ARGUMENT,
                      f"unsupported sample rate {cfg.sample_rate_hz}; expected {settings.sample_rate}")
    if cfg.channels != settings.channels:
        raise _Reject(grpc.StatusCode.INVALID_ARGUMENT,
                      f"unsupported channel count {cfg.channels}; expected {settings.channels}")


def _to_float32(audio: bytes, channels: int) -> np.ndarray:
    samples = np.frombuffer(audio, dtype="<i2").astype(np.float32) / 32768.0
    if channels > 1:
        samples = samples.reshape(-1, channels).mean(axis=1)
    return samples


class SpeechService(speech_pb2_grpc.SpeechServiceServicer):
    def __init__(self, engine, settings: ServerSettings):
        self.engine = engine
        self.settings = settings
        self.ready = engine is not None
        self.stopping = threading.Event()

    def Transcribe(self, request_iterator, context):
        t0 = time.perf_counter()
        log.info("request start peer=%s", context.peer())
        handle = None
        try:
            if not self.ready:
                raise _Reject(grpc.StatusCode.FAILED_PRECONDITION, "model is not ready")
            if self.stopping.is_set():
                raise _Reject(grpc.StatusCode.UNAVAILABLE, "server is shutting down")

            first = next(request_iterator, None)
            if first is None:
                raise _Reject(grpc.StatusCode.INVALID_ARGUMENT, "empty stream")
            if first.WhichOneof("payload") != "config":
                raise _Reject(grpc.StatusCode.INVALID_ARGUMENT,
                              "first message must carry the audio config")
            _validate_config(first.config, self.settings)
            channels = first.config.channels
            frame_bytes = SAMPLE_WIDTH * channels

            handle = self.engine.open_stream()
            chunks = 0
            samples_total = 0
            for msg in request_iterator:
                if self.stopping.is_set():
                    raise _Reject(grpc.StatusCode.UNAVAILABLE, "server is shutting down")
                if msg.WhichOneof("payload") != "audio":
                    raise _Reject(grpc.StatusCode.INVALID_ARGUMENT,
                                  "config may only be sent once, as the first message")
                if len(msg.audio) == 0 or len(msg.audio) % frame_bytes != 0:
                    raise _Reject(grpc.StatusCode.INVALID_ARGUMENT,
                                  "audio chunk is empty or not aligned to whole samples")
                chunks += 1
                samples_total += len(msg.audio) // frame_bytes
                seconds = samples_total / self.settings.sample_rate
                if seconds > self.settings.max_stream_seconds:
                    raise _Reject(grpc.StatusCode.RESOURCE_EXHAUSTED,
                                  f"stream exceeds {self.settings.max_stream_seconds:g}s limit")
                log.debug("chunk %d bytes=%d", chunks, len(msg.audio))
                text = handle.add_audio(_to_float32(msg.audio, channels))
                if chunks % self.settings.partial_every_n_chunks == 0:
                    log.info("partial after chunk %d (%.2fs audio)", chunks, seconds)
                    yield speech_pb2.Transcript(text=text, is_final=False,
                                                chunks_received=chunks, audio_seconds=seconds)

            text = handle.finalize()
            log.info("final chunks=%d audio=%.2fs server_time=%.3fs",
                     chunks, samples_total / self.settings.sample_rate, time.perf_counter() - t0)
            yield speech_pb2.Transcript(text=text, is_final=True, chunks_received=chunks,
                                        audio_seconds=samples_total / self.settings.sample_rate)
        except EngineBusy as e:
            log.warning("engine busy: %s", e)
            context.abort(grpc.StatusCode.UNAVAILABLE, str(e))
        except _Reject as e:
            log.warning("rejected: %s %s", e.code.name, e.message)
            context.abort(e.code, e.message)
        except Exception:
            log.exception("internal error")  # stack trace stays in the server log
            context.abort(grpc.StatusCode.INTERNAL, "internal error")
        finally:
            if handle is not None:
                handle.close()


def build_server(engine, settings: ServerSettings):
    """Create (not start) a gRPC server; returns (server, bound_port, service)."""
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=4))
    service = SpeechService(engine, settings)
    speech_pb2_grpc.add_SpeechServiceServicer_to_server(service, server)
    port = server.add_insecure_port(f"{settings.host}:{settings.port}")
    return server, port, service


def main(argv=None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    settings = load_settings(argv)
    logging.getLogger().setLevel(settings.log_level)

    from server.asr import ParakeetEngine
    log.info("loading model %s", settings.model_id)
    engine = ParakeetEngine(settings.model_id, settings.stream_wait_seconds)
    log.info("model loaded")

    server, port, service = build_server(engine, settings)
    server.start()
    log.info("ready on %s:%d", settings.host, port)

    done = threading.Event()

    def _stop(signum, _frame):
        log.info("signal %s: shutting down", signum)
        service.stopping.set()
        if hasattr(engine, "interrupt"):
            engine.interrupt()
        done.set()

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)
    done.wait()
    server.stop(grace=5).wait()
    if hasattr(engine, "close"):
        engine.close()
    log.info("stopped")


if __name__ == "__main__":
    main()
