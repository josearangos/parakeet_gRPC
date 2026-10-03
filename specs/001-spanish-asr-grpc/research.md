# Research: Spanish Streaming ASR over gRPC

## R1 — ASR library
- **Decision**: `parakeet-mlx` (v0.5.x) `from_pretrained("mlx-community/parakeet-tdt-0.6b-v3")`, loaded once at server start.
- **Rationale**: Native MLX implementation of Parakeet; default model is exactly the required one; minimal dependency set.
- **Alternatives**: NeMo (heavy, not MLX); `mlx-audio` (broader, more deps).

## R2 — Language
- **Decision**: No language flag; v3 is multilingual and detects language itself; Spanish is verified manually on a Spanish WAV.
- **Rationale**: Library exposes no language parameter. Non-Spanish speech may be transcribed in another language (documented).

## R3 — Incremental inference
- **Decision**: Use `model.transcribe_stream(context_size=(256,256), depth=1, keep_original_attention=False)` as a context manager per RPC. `add_audio(mx.array)` per chunk; read `transcriber.result.text` for partials (finalized + draft tokens); on stream close, read the result for the final transcript.
- **Rationale**: The library supports genuine streaming, so the simple re-transcribe fallback in FR-010 is not needed. Caveat (README): streaming switches the encoder to local attention, so output can differ slightly from offline transcription, and draft tokens can change between partials.
- **Alternatives**: Re-transcribe accumulated buffer with `model.transcribe` (fallback if streaming proves unstable; cost grows with length).

## R4 — Audio format
- **Decision**: PCM signed 16-bit little-endian, mono, 16 kHz default; server validates declared format against configured values, rejects others (no resampling). Convert int16 → float32 / 32768 → `mx.array` before `add_audio`.
- **Rationale**: Matches model's native rate; keeps client dependency-free (stdlib `wave`).
- **Alternatives**: Resample server-side (extra deps, hides errors).

## R5 — Contract shape
- **Decision**: `oneof payload { AudioConfig config = 1; bytes audio = 2; }` in `AudioChunk`—first message carries config, later ones audio. `Transcript` has `text`, `is_final`, `chunk_index`/`audio_seconds_processed` for observability.
- **Rationale**: Metadata is sent once, avoids per-chunk redundancy, and rejecting "config missing/changed mid-stream" is trivially testable. Keeps the user's `AudioChunk`/`Transcript` names.
- **Alternatives**: Metadata on every chunk (redundant; allows mid-stream drift).

## R6 — Partial cadence and long streams
- **Decision**: Emit a partial every N chunks (`PARTIAL_EVERY_N_CHUNKS`, default 1). Cap stream duration with `MAX_STREAM_SECONDS` (default 300) → `RESOURCE_EXHAUSTED`.
- **Rationale**: Clarification Q1 answered "A". Q2 (long streams) was not answered; this default is an assumption and can be revisited via `/speckit-clarify`.

## R7 — Concurrency and inference
- **Decision**: `grpc.server(ThreadPoolExecutor(max_workers=4))`; one shared model; a global lock serializes `add_audio`/finalize calls since MLX inference is not assumed thread-safe; per-RPC streaming context holds state.
- **Rationale**: Keeps stream state isolated with minimal code.

## R8 — Errors
- **Decision**: Map: bad/missing config, unsupported format, odd byte length → `INVALID_ARGUMENT`; model not ready → `FAILED_PRECONDITION`; too long → `RESOURCE_EXHAUSTED`; unexpected exception → `INTERNAL` with generic message (stack trace to server log only); server shutting down → `UNAVAILABLE`.

## R9 — Shutdown
- **Decision**: SIGINT/SIGTERM → `server.stop(grace=5)`; active RPCs cancelled; session contexts closed in `finally`.

## R10 — Metrics
- **Decision**: Client measures with `time.perf_counter()`: t0 at first chunk send; TTFT = first transcript − t0; total = final − t0; RTF = total / audio_duration; chunk count and chunk duration from the chunker. Server logs per-event lines via `logging`.

## R11 — Testing without model
- **Decision**: `server/asr.py` defines an `Engine` protocol; tests inject a fake engine that returns deterministic text per N samples, run an in-process gRPC server on an ephemeral port.
