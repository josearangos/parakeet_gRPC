"""Streams a WAV file or the microphone to the ASR server; prints transcripts + latency metrics.

Depends only on the gRPC contract; it never imports an ASR library.
"""
import argparse
import os
import shutil
import sys
import threading
import time
import wave

import grpc

import generated  # noqa: F401
import speech_pb2
import speech_pb2_grpc

from client import mic
from client.audio import iter_chunks, read_wav
from client.mic import MicError, open_mic
from client.metrics import RunMetrics

CLEAR_LINE = "\r\x1b[2K"


def _show_line(t) -> None:
    """WAV mode: one line per transcript."""
    print(f"[{'final' if t.is_final else 'partial'}] {t.text}")


def _show_live(t) -> None:
    """Mic mode: partials overwrite one live line; the final gets its own permanent line."""
    if t.is_final:
        sys.stdout.write(f"{CLEAR_LINE}[final] {t.text}\n")
    else:
        sys.stdout.write(f"{CLEAR_LINE}{_fit_live(t.text)}")
    sys.stdout.flush()


def _fit_live(text: str) -> str:
    """Trim a partial to the terminal width (keeping its end) so it never wraps.

    A wrapped line would leave earlier rows behind, since only the cursor's row is cleared.
    """
    prefix = "[partial] "
    room = shutil.get_terminal_size((80, 24)).columns - 1 - len(prefix)
    if len(text) <= room:
        return prefix + text
    return prefix + "…" + text[-(room - 1):] if room > 1 else prefix


def _config(rate: int, channels: int):
    return speech_pb2.AudioChunk(config=speech_pb2.AudioConfig(
        sample_rate_hz=rate, channels=channels, encoding=speech_pb2.PCM_S16LE))


def _stream(a, requests, show, marks, on_interrupt=None) -> None:
    """Shared loop: send `requests`, show each transcript, record first/final marks.

    Raises grpc.RpcError on RPC failure. Transcripts are received on a worker thread so a
    Ctrl+C in the main thread can call `on_interrupt` (once) and keep waiting for the final
    transcript; a gRPC response iterator cannot be resumed after being interrupted itself.
    """
    failure = []

    def receive():
        try:
            with grpc.insecure_channel(f"{a.host}:{a.port}") as channel:
                stub = speech_pb2_grpc.SpeechServiceStub(channel)
                for t in stub.Transcribe(requests):
                    now = time.perf_counter()
                    marks.setdefault("first", now)
                    show(t)
                    if t.is_final:
                        marks["final"] = now
        except BaseException as e:  # re-raised in the caller's thread
            failure.append(e)

    worker = threading.Thread(target=receive, daemon=True)
    worker.start()
    while worker.is_alive():
        try:
            worker.join(0.1)
        except KeyboardInterrupt:
            if on_interrupt is None:
                raise
            on_interrupt()
            on_interrupt = None  # a second Ctrl+C aborts
    if failure:
        raise failure[0]


def _run_wav(a) -> int:
    try:
        pcm, rate, channels, width = read_wav(a.wav)
    except (OSError, EOFError, wave.Error) as e:
        print(f"error: cannot read {a.wav} as an uncompressed PCM WAV file: {e}", file=sys.stderr)
        return 2
    if not pcm:
        print(f"error: {a.wav} contains no audio", file=sys.stderr)
        return 2
    if width != 2:
        print(f"error: only 16-bit WAV is supported (got {width * 8}-bit)", file=sys.stderr)
        return 2
    audio_s = len(pcm) / (rate * channels * width)
    chunks = list(iter_chunks(pcm, rate, channels, a.chunk_ms))

    marks = {}

    def requests():
        yield _config(a.sample_rate or rate, channels)
        for i, c in enumerate(chunks):
            if i == 0:
                marks["t0"] = time.perf_counter()
            yield speech_pb2.AudioChunk(audio=c)

    try:
        _stream(a, requests(), _show_line, marks)
    except grpc.RpcError as e:
        print(f"error: {e.code().name}: {e.details()}", file=sys.stderr)
        return 1

    if "t0" not in marks or "final" not in marks:
        print("error: no final transcript received", file=sys.stderr)
        return 1
    print(RunMetrics(marks["first"] - marks["t0"], marks["final"] - marks["t0"], audio_s,
                     len(chunks), a.chunk_ms / 1000).report())
    return 0


def _run_mic(a) -> int:
    try:
        source = open_mic(a.chunk_ms)
    except MicError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    marks = {}
    stats = {"chunks": 0, "bytes": 0}

    def requests():
        yield _config(mic.SAMPLE_RATE, mic.CHANNELS)
        for c in source.chunks():
            if stats["chunks"] == 0:
                marks["t0"] = time.perf_counter()
            stats["chunks"] += 1
            stats["bytes"] += len(c)
            yield speech_pb2.AudioChunk(audio=c)
        marks["stop"] = time.perf_counter()

    try:
        if sys.stdin.isatty():
            print("listening... press Enter to stop", file=sys.stderr)
            mic.stop_on_enter(source)
        else:
            print("listening... press Ctrl+C to stop", file=sys.stderr)
        _stream(a, requests(), _show_live, marks, on_interrupt=source.stop)
    except grpc.RpcError as e:
        sys.stdout.write("\n")
        print(f"error: {e.code().name}: {e.details()}", file=sys.stderr)
        if e.code() == grpc.StatusCode.RESOURCE_EXHAUSTED:
            print("note: the server's maximum stream length ended this session", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 1
    finally:
        source.close()
        if getattr(source, "overflowed", False):
            print("warning: audio was dropped by the device", file=sys.stderr)

    if "t0" not in marks or "final" not in marks:
        print("error: no final transcript received", file=sys.stderr)
        return 1
    audio_s = stats["bytes"] / (mic.SAMPLE_RATE * mic.CHANNELS * mic.SAMPLE_WIDTH)
    print(RunMetrics(marks["first"] - marks["t0"], marks["final"] - marks["t0"], audio_s,
                     stats["chunks"], a.chunk_ms / 1000).report())
    print(f"time from stop to final:  {marks['final'] - marks.get('stop', marks['final']):.3f} s")
    return 0


def main(argv=None) -> int:
    env = os.environ
    p = argparse.ArgumentParser(description="Spanish ASR gRPC client")
    p.add_argument("wav", nargs="?", help="16-bit PCM WAV file to transcribe")
    p.add_argument("--mic", action="store_true",
                   help="transcribe live from the default microphone (press Enter to stop)")
    p.add_argument("--host", default=env.get("GRPC_HOST", "localhost"))
    p.add_argument("--port", type=int, default=int(env.get("GRPC_PORT", 50051)))
    p.add_argument("--chunk-ms", type=int, default=int(env.get("CHUNK_SIZE", 500)),
                   help="audio per chunk in milliseconds")
    p.add_argument("--sample-rate", type=int, default=None,
                   help="override the sample rate declared to the server (testing)")
    a = p.parse_args(argv)

    if bool(a.wav) == a.mic:
        print("error: give exactly one of a WAV path or --mic", file=sys.stderr)
        return 2
    return _run_mic(a) if a.mic else _run_wav(a)


if __name__ == "__main__":
    sys.exit(main())
