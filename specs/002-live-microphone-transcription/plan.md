# Implementation Plan: Live Microphone Transcription

**Branch**: `002-live-microphone-transcription` | **Date**: 2026-10-03 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/002-live-microphone-transcription/spec.md`

## Summary

Add a microphone audio source to the existing client. A `--mic` flag makes the client capture 16 kHz mono 16-bit PCM from the default input device in `--chunk-ms` blocks and feed them, as they are captured, into the same `Transcribe` bidirectional stream the WAV mode uses. Partials overwrite one live terminal line; Enter (or Ctrl+C) stops capture, closes the stream, and the final transcript is printed on its own line followed by the usual metrics. **The server, the `.proto`, and the WAV flow are untouched.** See [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.13 (as feature 001)

**Primary Dependencies**: existing (`grpcio`, `protobuf`) + `sounddevice` (PortAudio bindings; audio capture only, no ASR). Imported lazily so WAV mode and tests need neither a microphone nor PortAudio.

**Storage**: N/A (audio is never written to disk)

**Testing**: `pytest`; model-free and device-free. A fake audio source replaces the microphone; the existing in-process gRPC server with fake engine is reused for the contract path.

**Target Platform**: macOS, Apple Silicon, terminal; microphone permission granted to the terminal app

**Project Type**: Two-process client/server (unchanged); change confined to the client

**Performance Goals**: None gated (constitution IV); spec SC-001..SC-003 are observed manually with a real mic

**Constraints**: No contract change; no new services; capture must never block on the network (separate capture callback and queue)

**Scale/Scope**: One live session at a time, bounded by the server's existing `MAX_STREAM_SECONDS`

## Constitution Check

| Principle | Status | Notes |
|---|---|---|
| I. Contract-first | PASS | `speech.proto` unchanged; microphone is just another producer of `AudioChunk`. See [contracts/](contracts/) |
| II. Separation | PASS | Client gains an audio-capture dependency only; still imports no MLX/Parakeet/ASR library. Constitution anticipates a "microphone source" |
| III. Honest streaming | PASS | Server behavior unchanged; README gets a note that live partials may be revised and are re-decoded by the server, not true incremental decoding |
| IV. Measurable latency | PASS | Same metrics, monotonic clock, plus stop-to-final delay in mic mode |
| V. Simplicity/config | PASS | One flag, one small module; one new dependency justified in research.md (no stdlib audio capture exists); chunk size reuses `--chunk-ms` |
| Scope exclusions | PASS | No telephony, auth, web UI, or infrastructure added |

**Post-design re-check**: PASS; no Complexity Tracking entries.

## Project Structure

### Documentation (this feature)

```text
specs/002-live-microphone-transcription/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── client-cli.md
└── tasks.md             # created by /speckit-tasks
```

### Source Code (repository root)

```text
client/
├── client.py      # modified: `--mic` flag, wav positional becomes optional, shared display/metrics path
├── mic.py         # new: MicSource (capture -> queue -> chunk iterator), stop handling
├── audio.py       # unchanged
└── metrics.py     # unchanged (stop-to-final computed in client.py and printed beside the report)
tests/
├── test_client_mic.py   # new: fake source -> in-process server; live-line display; error paths
└── fakes.py             # extended with a fake mic source if needed
requirements.txt         # + sounddevice
README.md                # + microphone section
```

**Structure Decision**: Extend the existing client package with one new module; no new top-level directories.

## Complexity Tracking

No constitution violations.
