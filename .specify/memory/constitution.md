# Spanish Streaming ASR over gRPC Constitution

## Core Principles

### I. Contract-First gRPC Streaming
The service contract lives in `proto/speech.proto` and is written before any client or server
code. It MUST define `SpeechService`, the `Transcribe` RPC as bidirectional streaming
(`stream AudioChunk` → `stream Transcript`), `AudioChunk`, and `Transcript`. `AudioChunk` MUST
carry enough metadata (e.g. sample rate, encoding) for the server to interpret the stream;
`Transcript` MUST carry text and a partial/final flag. Generated code MUST be reproducible from
the `.proto` and MUST NOT be hand-edited. Rationale: the learning goal is to understand typed
contracts and streaming RPC; a single call must carry many chunks in and many transcripts out.

### II. Separation of Responsibilities
The layout is `proto/`, `client/`, `server/`. The server exclusively owns model loading and
inference. The client MUST NOT import MLX, Parakeet, or any ASR library; it only reads audio,
streams chunks, prints transcripts, and measures latency. The client MUST depend only on the
gRPC contract so the WAV source can later be swapped for a microphone or telephony source.
Rationale: demonstrates an ML model as an independent microservice.

### III. Honest Streaming Semantics
The server MUST buffer audio per stream and MUST NOT treat each chunk as an independent audio
file. If the MLX Parakeet API lacks true incremental decoding, the implementation MUST use the
simplest reasonable buffering strategy (e.g. re-transcribing the accumulated buffer) and the
README MUST state this limitation. Results MUST be marked partial or final accurately, and a
final transcript MUST be emitted after the client closes its stream. Code, logs, and docs MUST
NOT claim true streaming inference unless it is actually performed. Rationale: understanding
real latency behavior is the point of the exercise.

### IV. Measurable Latency
The client MUST report audio duration, time to first transcript, total processing time, RTF
(`processing_time / audio_duration`), and number of chunks. Metrics MUST be measured with a
monotonic clock. No production performance targets are set; metrics exist to observe behavior,
not to gate releases.

### V. Simplicity & Configurability
Prefer simple, readable Python and minimal dependencies. Abstractions MUST be justified by a
concrete present need (YAGNI). Model identifier (default `mlx-community/parakeet-tdt-0.6b-v3`),
gRPC host/port, chunk size, sample rate, and other runtime parameters MUST be configurable
(CLI flags and/or environment variables) rather than hardcoded. Rationale: prioritize
understanding over framework complexity.

## Technology & Scope Constraints

- Language and stack: Python, gRPC, Protocol Buffers, MLX-compatible tooling on Apple Silicon.
- ASR model: `mlx-community/parakeet-tdt-0.6b-v3` for Spanish transcription.
- The project MUST run locally with no external infrastructure.
- Explicitly out of scope (MUST NOT be added): Kubernetes, Docker, AWS/GCP deployment, Kafka,
  RabbitMQ, Redis, FastAPI, LLM, TTS, telephony integration, authentication, production
  observability, and complex CI/CD.
- README MUST explain: why gRPC, why bidirectional streaming, the `.proto` contract, audio
  buffering, Parakeet integration, latency measurement, and MLX Parakeet limitations.

## Development Workflow & Quality Gates

- Suggested structure: `proto/`, `server/{server,asr}.py`, `client/{client,audio}.py`, `tests/`,
  `requirements.txt`, `README.md`, `.gitignore`. Deviations require a stated technical reason.
- Tests MUST cover chunking/buffering logic and the streaming contract (multiple chunks in,
  multiple transcripts out, final transcript after stream end) where practical without
  requiring model download; model-dependent checks are run manually on a Spanish WAV.
- Every change MUST be checked against the acceptance criteria AC1–AC9 of the project brief
  and against the principles above.
- Out-of-scope additions are rejected in review even if convenient.

## Governance

This constitution supersedes other project practices. Amendments MUST be made by editing this
file with a documented rationale, an updated Sync Impact Report, and a version bump following
semantic versioning: MAJOR for removed or redefined principles, MINOR for added principles or
materially expanded guidance, PATCH for clarifications. Reviews and plans MUST verify
compliance with the principles; any deviation (e.g. extra dependency or abstraction) MUST be
justified in writing in the plan or PR.

**Version**: 1.0.0 | **Ratified**: 2026-10-02 | **Last Amended**: 2026-10-02
