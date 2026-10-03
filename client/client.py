"""Streams a WAV file to the ASR server and prints transcripts + latency metrics.

Depends only on the gRPC contract; it never imports an ASR library.
"""
import argparse
import os
import sys
import time

import grpc

import generated  # noqa: F401
import speech_pb2
import speech_pb2_grpc

from client.audio import iter_chunks, read_wav
from client.metrics import RunMetrics


def main(argv=None) -> int:
    env = os.environ
    p = argparse.ArgumentParser(description="Spanish ASR gRPC client")
    p.add_argument("wav")
    p.add_argument("--host", default=env.get("GRPC_HOST", "localhost"))
    p.add_argument("--port", type=int, default=int(env.get("GRPC_PORT", 50051)))
    p.add_argument("--chunk-ms", type=int, default=int(env.get("CHUNK_SIZE", 500)),
                   help="audio per chunk in milliseconds")
    p.add_argument("--sample-rate", type=int, default=None,
                   help="override the sample rate declared to the server (testing)")
    a = p.parse_args(argv)

    pcm, rate, channels, width = read_wav(a.wav)
    if width != 2:
        print(f"error: only 16-bit WAV is supported (got {width * 8}-bit)", file=sys.stderr)
        return 2
    audio_s = len(pcm) / (rate * channels * width)
    chunks = list(iter_chunks(pcm, rate, channels, a.chunk_ms))

    marks = {}

    def requests():
        yield speech_pb2.AudioChunk(config=speech_pb2.AudioConfig(
            sample_rate_hz=a.sample_rate or rate, channels=channels,
            encoding=speech_pb2.PCM_S16LE))
        for i, c in enumerate(chunks):
            if i == 0:
                marks["t0"] = time.perf_counter()
            yield speech_pb2.AudioChunk(audio=c)

    try:
        with grpc.insecure_channel(f"{a.host}:{a.port}") as channel:
            stub = speech_pb2_grpc.SpeechServiceStub(channel)
            for t in stub.Transcribe(requests()):
                now = time.perf_counter()
                marks.setdefault("first", now)
                label = "final" if t.is_final else "partial"
                print(f"[{label}] {t.text}")
                if t.is_final:
                    marks["final"] = now
    except grpc.RpcError as e:
        print(f"error: {e.code().name}: {e.details()}", file=sys.stderr)
        return 1

    if "t0" not in marks or "final" not in marks:
        print("error: no final transcript received", file=sys.stderr)
        return 1
    print(RunMetrics(marks["first"] - marks["t0"], marks["final"] - marks["t0"], audio_s,
                     len(chunks), a.chunk_ms / 1000).report())
    return 0


if __name__ == "__main__":
    sys.exit(main())
