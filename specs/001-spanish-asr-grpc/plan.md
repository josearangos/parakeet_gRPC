# Implementation Plan: Spanish Streaming Speech-to-Text Service

**Branch**: `001-spanish-asr-grpc` | **Date**: 2026-10-03 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/001-spanish-asr-grpc/spec.md`

## Summary

A local gRPC microservice: the server loads Parakeet TDT 0.6B v3 once (via the `parakeet-mlx` library) and exposes one bidirectional-streaming RPC, `Transcribe(stream AudioChunk) returns (stream Transcript)`. A WAV client chunks audio, streams it, prints partial/final transcripts and reports latency metrics. Partials come from the library's streaming context (`transcribe_stream`) on one dedicated MLX thread (one stream at a time, bounded wait), emitted every N chunks; a final transcript is sent when the client closes the stream. See [research.md](research.md) for decisions.

## Technical Context

**Language/Version**: Python 3.13 (3.12 also fine; avoid 3.14 until MLX wheels are confirmed)

**Primary Dependencies**: `grpcio`, `grpcio-tools` (dev, codegen), `protobuf`, `parakeet-mlx` (brings `mlx`, `numpy`, `librosa`, `huggingface-hub`)

**Storage**: N/A (model weights cached by Hugging Face hub on first use)

**Testing**: `pytest`; model-free tests use a fake ASR engine injected into the servicer and an in-process gRPC server

**Target Platform**: macOS, Apple Silicon (arm64), local only

**Project Type**: Two-process client/server (CLI client, gRPC server) with a shared `.proto`

**Performance Goals**: None gated (constitution IV); metrics observed only

**Constraints**: Local, no external infrastructure; minimal dependencies; no generated-code edits

**Scale/Scope**: Single developer; a few concurrent streams for isolation only; per-stream max duration (configurable, default 300 s) to bound memory

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Contract-first | PASS | `proto/speech.proto` written first; copy in [contracts/speech.proto](contracts/speech.proto); generated code reproducible via one command, not hand-edited |
| II. Separation | PASS | Client imports only grpc/generated code/wave/numpy-free stdlib; MLX/Parakeet only in `server/asr.py` |
| III. Honest streaming | PASS | Uses real streaming context; README states it uses local-attention approximation and that partials may be revised; per-stream state, final after stream close |
| IV. Measurable latency | PASS | Client reports all six metrics with `time.monotonic()`/`perf_counter` |
| V. Simplicity/config | PASS | stdlib `argparse` + env vars; no framework; one extra abstraction (engine interface) justified by model-free tests |
| Scope exclusions | PASS | None added |

**Post-design re-check**: PASS (no new violations; no Complexity Tracking entries).

## Project Structure

### Documentation (this feature)

```text
specs/001-spanish-asr-grpc/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── speech.proto
└── tasks.md             # created by /speckit-tasks
```

### Source Code (repository root)

```text
proto/
└── speech.proto
generated/               # speech_pb2.py, speech_pb2_grpc.py (generated, git-tracked or regenerated via script)
server/
├── server.py            # gRPC servicer, validation, status codes, lifecycle
├── asr.py               # Parakeet engine + per-stream session (only place importing MLX)
└── config.py            # env/CLI settings
client/
├── client.py            # streams chunks, prints transcripts, metrics
└── audio.py             # WAV reading + chunking (stdlib wave)
scripts/
└── gen_proto.sh         # reproducible codegen
tests/
├── test_chunking.py
├── test_validation.py
└── test_streaming_contract.py
requirements.txt
README.md
.gitignore
```

**Structure Decision**: Constitution layout (`proto/`, `server/`, `client/`, `tests/`) plus `generated/` and `scripts/gen_proto.sh` so codegen is a single reproducible command; `server/config.py` is shared-small and avoids env parsing in `server.py`.

## Complexity Tracking

No constitution violations.
