---

description: "Task list for Live Microphone Transcription"
---

# Tasks: Live Microphone Transcription

**Input**: Design documents from `/specs/002-live-microphone-transcription/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/client-cli.md, quickstart.md

**Tests**: Included (plan.md and the constitution require model-free, device-free tests for new streaming logic).

**Organization**: Grouped by user story. Server, `proto/speech.proto` and the WAV flow MUST NOT change (FR-008, FR-011).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1, US2, US3 (from spec.md)

## Phase 1: Setup

- [X] T001 Add `sounddevice` to `requirements.txt` (it is already listed in `requirements-record.txt`; do not add numpy or other packages)
- [X] T002 [P] Create `client/mic.py` with module docstring "Microphone capture source (audio capture only; no ASR library)" and imports; `sounddevice` MUST be imported lazily inside the real source so WAV mode and tests need no PortAudio or device

## Phase 2: Foundational (blocks all stories)

- [X] T003 Refactor `client/client.py`: make the `wav` positional optional (`nargs="?"`), add `--mic` flag; exactly one of `wav` / `--mic` is required, otherwise print `error: ...` to stderr and return 2 (per contracts/client-cli.md). Keep all WAV behavior and existing messages identical
- [X] T004 Refactor `client/client.py` so the stream-and-print loop (send `AudioConfig{16000,1,PCM_S16LE}` first, iterate `stub.Transcribe`, record `t0`/`first`/`final` marks, handle `grpc.RpcError` with `error: CODE: details` and exit 1) is a shared function usable by both WAV and mic sources; existing tests in `tests/test_client_wav.py` must still pass

**Checkpoint**: `pytest` passes unchanged.

## Phase 3: User Story 1 - Speak and see live transcription (P1) MVP

**Goal**: `--mic` captures live audio, streams chunks as captured, shows partials on one live line, and prints the final transcript after Enter/Ctrl+C.

**Independent Test**: Server running; `python -m client.client --mic`; speak Spanish; partials appear before Enter; `[final] ...` after.

### Tests for User Story 1

- [X] T005 [P] [US1] In `tests/test_client_mic.py`, add a test that feeds a fake chunk source (list of PCM chunks) through the shared client path against the in-process server with `FakeEngine` (see `tests/conftest.py` `make_server`) and asserts: first message is the config with 16000/1/PCM_S16LE, N chunks in, partials then exactly one final last
- [X] T006 [P] [US1] In `tests/test_client_mic.py`, add a test for display: partials are written as `\r` + clear-line escape (`\x1b[2K`) + `[partial] text` with no newline; the final is printed as `[final] text` on its own line (capsys)

### Implementation for User Story 1

- [X] T007 [US1] In `client/mic.py`, implement `MicSource`: opens `sounddevice.RawInputStream(samplerate=16000, channels=1, dtype="int16", blocksize=16000*chunk_ms//1000, callback=...)`; the callback only does `queue.Queue.put(bytes(indata))`; provides `chunks()` generator that yields queued bytes until the stop event is set and the queue is drained; `stop()` sets the event; context-manager `__exit__` always stops and closes the stream (releases the device)
- [X] T008 [US1] In `client/mic.py`, add a daemon thread helper that waits on `sys.stdin.readline()` and calls `MicSource.stop()` (Enter to stop); `KeyboardInterrupt` in `client/client.py` also calls `stop()` and then still awaits the final transcript
- [X] T009 [US1] In `client/client.py`, wire `--mic`: print `listening... press Enter to stop` to stderr, build the request generator from `MicSource.chunks()` (config message first, then `AudioChunk(audio=...)`), reuse the shared loop from T004; count `chunks_sent` and `bytes_captured`
- [X] T010 [US1] In `client/client.py`, implement the clarified display rule (FR-004): partial -> `\r\x1b[2K[partial] {text}` written without newline and flushed; final -> clear the live line, then `[final] {text}` with newline; WAV mode keeps its current one-line-per-transcript output

**Checkpoint**: T005/T006 pass; a manual live run works (quickstart scenario 1).

## Phase 4: User Story 2 - Clear feedback and graceful failure (P2)

**Goal**: Every failure yields a readable `error:` message, exit code per contract, and a released microphone.

**Independent Test**: Run `--mic` with no device / server stopped; confirm message and clean exit.

### Tests for User Story 2

- [X] T011 [P] [US2] In `tests/test_client_mic.py`, test that a source whose open raises (simulating no input device / `PortAudioError`) makes `client.main(["--mic"])` return 2 with `error:` on stderr, no traceback, and without contacting the server
- [X] T012 [P] [US2] In `tests/test_client_mic.py`, test that an unreachable server (closed port) returns 1 with `error:` and that the fake source was closed (device released)
- [X] T013 [P] [US2] In `tests/test_client_mic.py`, test usage errors: no args, and both a WAV path and `--mic` -> return 2 with `error:`; and an immediate stop (zero chunks) ends without a traceback

### Implementation for User Story 2

- [X] T014 [US2] In `client/mic.py`, catch `sounddevice.PortAudioError`, `OSError` and "no input device" (`sounddevice.query_devices(kind="input")` failure) when opening and raise a small `MicError` with an actionable message (mention macOS Microphone permission for the terminal)
- [X] T015 [US2] In `client/client.py`, catch `MicError` before any channel/server use -> `error: ...` on stderr, return 2; ensure `MicSource` is closed on every exit path (normal, `grpc.RpcError`, `KeyboardInterrupt`)
- [X] T016 [US2] In `client/client.py`, when the server's max stream duration ends the session (RPC status from the existing limit), print a short note saying the limit ended the session, then still show the final transcript if received (spec edge case)

**Checkpoint**: T011-T013 pass; quickstart scenarios 2-4 behave as written.

## Phase 5: User Story 3 - Latency metrics for live sessions (P3)

**Goal**: Same metrics block as file mode after a live session, plus stop-to-final delay.

**Independent Test**: Complete one `--mic` session; metrics block printed.

- [X] T017 [P] [US3] In `tests/test_client_mic.py`, test that a fake-source session prints the metrics block (audio duration = bytes_captured / (16000*2), chunk count, time to first transcript) and a `time from stop to final:` line, using `time.perf_counter` marks
- [X] T018 [US3] In `client/client.py`, for `--mic` build `RunMetrics` from `bytes_captured`, `chunks_sent`, `chunk_ms`, `t0` (first chunk sent) and `final`; record `t_stop` when capture stops and print `time from stop to final: X.XXX s` after `RunMetrics.report()` (no change to `client/metrics.py`)

**Checkpoint**: Metrics shown for mic and WAV sessions.

## Phase 6: Polish & Cross-Cutting

- [X] T019 [P] Update `README.md`: microphone section (command, Enter/Ctrl+C to stop, macOS permission, live-line display), add `--mic` to the flags table, and a note that live partials come from the server re-decoding buffered audio and may be revised (constitution III); mention RTF is less meaningful for live speech
- [X] T020 [P] Record the stop-action decision (`--mic`, Enter to stop) in `specs/002-live-microphone-transcription/spec.md` under Clarifications and FR-005/FR-001 wording if still consistent
- [X] T021 Run `pytest` (all prior tests pass, SC-006) and confirm `git diff --stat` shows no changes under `server/`, `proto/`, or `generated/`
- [ ] T022 Manual validation with a real microphone and Spanish speech per `specs/002-live-microphone-transcription/quickstart.md` scenarios 1-5 (SC-001..SC-005), noting results in the quickstart

## Dependencies & Execution Order

- Phase 1 -> Phase 2 -> Phase 3 (US1, MVP) -> Phase 4 (US2) and Phase 5 (US3, can follow US1 in either order) -> Phase 6.
- US2 and US3 depend on the MicSource and shared loop from US1 but not on each other.
- T007 -> T008 -> T009 -> T010 (same files, sequential). Tests T005/T006 can be written first and should fail before T007-T010.

## Parallel Opportunities

- T001 with T002; T005 with T006; T011, T012, T013 together; T017 alongside T014-T016 (different files); T019 with T020.

## Implementation Strategy

- **MVP**: Phases 1-3 (live transcription with Enter-to-stop). Validate with quickstart scenario 1, then add error handling (US2) and metrics (US3).

## Phase 7: Convergence

- [X] T023 Add a test in `tests/test_client_mic.py` that monkeypatches `sounddevice` (query_devices / RawInputStream raising) and asserts `MicSource.start()` in `client/mic.py` raises `MicError` with the macOS Microphone-permission hint and leaves no open stream, per FR-007 / US2/AC2 (partial)
- [X] T024 In `client/client.py` `_run_mic`, print `listening... press Enter to stop` only when stdin is a terminal; otherwise print `listening... press Ctrl+C to stop`, so the stop hint is never wrong when Enter is not listened for, per FR-006 / US2/AC1 (partial)
- [X] T025 In `client/mic.py` `MicSource._on_audio`, record when PortAudio reports an input overflow in `status` and have `client/client.py` print a one-time `warning: audio was dropped by the device` to stderr after the session, so dropped audio is not silent, per FR-002 / spec edge case "capture continues without dropping audio" (partial)
- [X] T026 In `client/client.py` `_show_live`, trim each live partial to the terminal width (keep the end of the text, prefix `[partial] …`) so it never wraps and stacks rows, per FR-004 / clarification Q1 (partial; found in manual run T022)
