# Tasks: Spanish Streaming Speech-to-Text Service

**Input**: Design documents from `/specs/001-spanish-asr-grpc/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/speech.proto, quickstart.md

**Tests**: Included. The spec (FR-018) and constitution require model-free tests for chunking/buffering and the streaming contract.

**Organization**: Grouped by user story. Paths are relative to the repository root.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on incomplete tasks)
- **[Story]**: US1–US5 map to the user stories in spec.md

## Phase 1: Setup

- [X] T001 Create directories `proto/`, `generated/`, `server/`, `client/`, `scripts/`, `tests/` with `__init__.py` in `server/`, `client/`, `tests/`
- [X] T002 [P] Create `requirements.txt` with `grpcio`, `grpcio-tools`, `protobuf`, `parakeet-mlx`, `pytest` (no other dependencies)
- [X] T003 [P] Create `.gitignore` (`.venv/`, `__pycache__/`, `.pytest_cache/`, `*.wav` except `samples/`, `generated/*_pb2*.py`)
- [X] T004 [P] Create a README.md skeleton in `README.md` with the section headings required by the constitution (why gRPC, why bidirectional streaming, the .proto contract, audio buffering, Parakeet integration, latency measurement, MLX Parakeet limitations, RPC/gRPC/Protobuf/HTTP2 explainer)

---

## Phase 2: Foundational (blocks all user stories)

- [X] T005 Copy `specs/001-spanish-asr-grpc/contracts/speech.proto` to `proto/speech.proto` (package `speech.v1`; `service SpeechService { rpc Transcribe(stream AudioChunk) returns (stream Transcript); }`; `AudioChunk` oneof `config`/`audio`; `Transcript` fields `text`, `is_final`, `chunks_received`, `audio_seconds`)
- [X] T006 Create `scripts/gen_proto.sh` running `python -m grpc_tools.protoc -I proto --python_out=generated --grpc_python_out=generated proto/speech.proto`, and a hand-written `generated/__init__.py` that appends the `generated/` directory to `sys.path` (so the generated `import speech_pb2` resolves without editing generated files)
- [X] T007 Run `scripts/gen_proto.sh` to produce `generated/speech_pb2.py` and `generated/speech_pb2_grpc.py`; verify `python -c "import generated; import speech_pb2, speech_pb2_grpc"` works
- [X] T008 [P] Create `server/config.py`: dataclass `ServerSettings` read from env with defaults `MODEL_ID=mlx-community/parakeet-tdt-0.6b-v3`, `GRPC_HOST=localhost`, `GRPC_PORT=50051`, `AUDIO_SAMPLE_RATE=16000`, `AUDIO_CHANNELS=1`, `PARTIAL_EVERY_N_CHUNKS=1`, `MAX_STREAM_SECONDS=300`, plus argparse flag overrides (flags > env > defaults)
- [X] T009 [P] Create `client/audio.py`: `read_wav(path) -> (pcm_bytes, sample_rate, channels, sample_width)` using stdlib `wave`, and `iter_chunks(pcm_bytes, sample_rate, channels, chunk_ms)` yielding frame-aligned byte chunks (never splits a sample)
- [X] T010 [P] Create `server/asr.py` Engine interface: `Engine` protocol with `open_stream() -> StreamHandle`; `StreamHandle` with `add_audio(samples_float32) -> str` (current text), `finalize() -> str`, `close()`; no MLX import at module top level other than inside `ParakeetEngine`
- [X] T011 [P] Test chunking in `tests/test_chunking.py`: 10 s of 16 kHz mono PCM at 500 ms → 20 chunks; remainder chunk shorter; chunk boundaries are multiples of `2 × channels` bytes; concatenated chunks equal input; chunk size 0/negative raises `ValueError`

**Checkpoint**: contract generated, config/chunking/engine interface in place.

---

## Phase 3: User Story 1 — Stream Spanish audio and receive a final transcript (P1) 🎯 MVP

**Goal**: One streaming call carries many chunks in; at least a final transcript comes out.

**Independent Test**: Start server, run client on a Spanish WAV, see a final transcript. Model-free: contract test with a fake engine.

- [X] T012 [P] [US1] Create fake engine `FakeEngine` in `tests/fakes.py` (returns text like `"palabra N"` per call to `add_audio`, final text joins all)
- [X] T013 [P] [US1] Write `tests/test_streaming_contract.py`: in-process gRPC server on port 0 with `FakeEngine`; send config + 5 audio chunks; assert ≥1 transcript received, exactly one `is_final=True`, and it is the last message; assert a second concurrent stream has an isolated transcript
- [X] T014 [US1] Implement `ParakeetEngine` in `server/asr.py`: `from_pretrained(model_id)` once in constructor; `open_stream()` wraps `model.transcribe_stream(context_size=(256,256), depth=1, keep_original_attention=False)` as a context manager; `add_audio` converts int16 → float32 / 32768 → `mx.array` and returns `transcriber.result.text`; `finalize()` returns final text; a module-level `threading.Lock` serializes MLX calls
- [X] T015 [US1] Implement `SpeechService(speech_pb2_grpc.SpeechServiceServicer).Transcribe` in `server/server.py`: first message must be `config`, create `StreamSession`, for each audio chunk convert bytes→int16 samples and call engine; at stream end yield one `Transcript(is_final=True)`; close the handle in `finally`
- [X] T016 [US1] Add `serve()`/`main()` in `server/server.py`: build settings, load `ParakeetEngine` before `server.start()` (log `ready`), `grpc.server(ThreadPoolExecutor(max_workers=4))`, bind `GRPC_HOST:GRPC_PORT`; runnable via `python -m server.server`
- [X] T017 [US1] Implement `client/client.py`: argparse (`wav`, `--host`, `--port`, `--chunk-ms` default 500, env `GRPC_HOST`/`GRPC_PORT`/`CHUNK_SIZE`), request generator sending config then audio chunks, print each transcript with `[partial]`/`[final]` label; imports only `grpc`, `generated`, `client.audio` (no MLX/Parakeet)
- [X] T018 [US1] Manually verify on a Spanish WAV per `quickstart.md` scenario 1 and note the result in `README.md`

**Checkpoint**: MVP — end-to-end Spanish transcription over one bidirectional call.

---

## Phase 4: User Story 2 — Partial results while audio is arriving (P2)

**Goal**: Partials every N chunks, labeled partial, one final at end.

**Independent Test**: With a fake engine, stream 6 chunks with N=2 → partials after chunks 2, 4, 6 then final.

- [X] T019 [P] [US2] Add tests in `tests/test_streaming_contract.py`: `PARTIAL_EVERY_N_CHUNKS=2` yields partials after chunks 2/4/6 with `is_final=False` and increasing `chunks_received`/`audio_seconds`; partial emitted before client closes the stream
- [X] T020 [US2] In `server/server.py`, yield `Transcript(text, is_final=False, chunks_received, audio_seconds)` after every N-th chunk (setting `PARTIAL_EVERY_N_CHUNKS`); emit partials even if the text is empty
- [X] T021 [US2] Document in `README.md` (audio buffering / limitations): uses the library's streaming context with local attention, draft tokens may change between partials, final may differ slightly from offline transcription; also note Parakeet v3 auto-detects language

**Checkpoint**: Partial + final behavior verified.

---

## Phase 5: User Story 3 — Latency and chunk metrics (P2)

**Goal**: Client reports six metrics; server logs lifecycle events.

**Independent Test**: Unit-test metrics math; run client and see the report.

- [X] T022 [P] [US3] Create `client/metrics.py` with `RunMetrics` dataclass and functions computing TTFT, total time, `rtf = total / audio_duration`, chunk count, chunk duration, audio duration (`time.perf_counter` for timing)
- [X] T023 [P] [US3] Write `tests/test_metrics.py`: RTF = 2.0 for 20 s processing of 10 s audio; chunk count = ceil(audio/chunk); TTFT is measured from the first chunk send
- [X] T024 [US3] Integrate metrics into `client/client.py`: start timer when first audio chunk is sent, record first transcript and final transcript times, print a metrics block at the end
- [X] T025 [US3] Add `logging` lines in `server/server.py` for request start, config accepted, each chunk (count only, DEBUG), each transcript emitted, final result with server-side duration, and errors (no stack traces to clients)

---

## Phase 6: User Story 4 — Clear errors for bad input (P3)

**Goal**: Categorized gRPC errors; server stays up.

**Independent Test**: Contract tests for each invalid case.

- [X] T026 [P] [US4] Write `tests/test_validation.py` covering: missing config first message → `INVALID_ARGUMENT`; unsupported sample rate (8000), channels (2), encoding (`ENCODING_UNSPECIFIED`) → `INVALID_ARGUMENT`; odd-length audio chunk → `INVALID_ARGUMENT`; second `config` mid-stream → `INVALID_ARGUMENT`; empty stream → `INVALID_ARGUMENT`; stream longer than `MAX_STREAM_SECONDS` → `RESOURCE_EXHAUSTED`; engine raising → `INTERNAL` with no traceback text in details; server usable after each error
- [X] T027 [US4] Implement validation in `server/server.py` using `context.abort(grpc.StatusCode.X, message)` per `research.md` R8; wrap engine calls in `try/except Exception` → log with `logging.exception`, abort `INTERNAL` with message "internal error"
- [X] T028 [US4] Return `FAILED_PRECONDITION` if the engine is not ready (flag set only after model load) and `UNAVAILABLE` when the server is shutting down
- [X] T029 [US4] Make the client print gRPC error code + details cleanly (catch `grpc.RpcError`, exit code 1, no traceback)

---

## Phase 7: User Story 5 — Configuration and graceful shutdown (P3)

**Goal**: Everything configurable; clean stop.

**Independent Test**: Non-default port works; Ctrl-C during a stream exits ≤5 s.

- [X] T030 [P] [US5] Write `tests/test_config.py`: flags override env, env overrides defaults, defaults match spec (`localhost`, `50051`, 16000, 1, model id)
- [X] T031 [US5] Install SIGINT/SIGTERM handlers in `server/server.py` calling `server.stop(grace=5)` then waiting for termination; ensure `finally` closes stream handles
- [X] T032 [US5] Verify the model is loaded exactly once: log `model loaded` once at startup and assert in a test that `FakeEngine` constructor is called once across 5 RPCs
- [ ] T033 [US5] Manually verify quickstart scenarios 3–4 (non-default port, 5 consecutive runs, Ctrl-C mid-stream) and note results in `README.md`

---

## Phase 8: Polish & Cross-Cutting

- [X] T034 [P] Complete `README.md`: why gRPC, why bidirectional streaming, the `.proto` walkthrough, buffering, Parakeet integration, latency measurement, limitations (long streams capped at `MAX_STREAM_SECONDS`; non-Spanish speech auto-detected), and the RPC / gRPC / Protocol Buffers / HTTP/2 / bidirectional streaming / Parakeet explainer from the project brief
- [X] T035 [P] Add a short "future TLS/auth/quotas" note in `README.md` (design allows `grpc.ssl_server_credentials` and interceptors; nothing implemented)
- [X] T036 Run `pytest` and confirm all tests pass without downloading the model; run quickstart end-to-end once
- [X] T037 Constitution check: grep `client/` for `mlx`/`parakeet` imports (must be none) and confirm `generated/*_pb2*.py` are unmodified (regenerate and diff)

---

## Dependencies & Execution Order

- Phase 1 → Phase 2 → user stories → Polish.
- US1 is the MVP and a prerequisite for US2–US5 (they extend `server/server.py` and `client/client.py`).
- After US1: US2, US3, US4, US5 are largely independent; tasks touching `server/server.py` (T020, T025, T027, T028, T031) must be sequenced, not parallel.
- Within a story: tests (T012–T013, T019, T023, T026, T030) before implementation.

## Parallel Opportunities

- Phase 1: T002, T003, T004.
- Phase 2: T008, T009, T010, T011 after T007.
- US1: T012 and T013 together.
- US3: T022 and T023; US4 T026 alongside US3 client work.

## Implementation Strategy

1. MVP: Phases 1–3 (US1) — validate manually on a Spanish WAV.
2. Add US2 (partials), then US3 (metrics).
3. Add US4 (errors) and US5 (config/shutdown).
4. Polish and README.
