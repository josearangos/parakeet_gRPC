# Feature Specification: Spanish Streaming Speech-to-Text Service

**Feature Branch**: `001-spanish-asr-grpc`

**Created**: 2026-10-03

**Status**: Draft

**Input**: User description: "Spanish ASR + gRPC System — a local ML microservice that exposes Spanish speech-to-text through a streaming gRPC API, using the Parakeet TDT 0.6B v3 model on Apple Silicon, with latency metrics."

## Clarifications

### Session 2026-10-03

- Q: When should the service emit a partial transcript while audio is still arriving? → A: After every N chunks received (N configurable, default 1 chunk per partial)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Stream Spanish audio and receive a transcript (Priority: P1)

A developer runs the speech service locally, then runs a client against a Spanish audio file. The client splits the audio into small chunks, sends them progressively over a single streaming call, and prints the text returned by the service, ending with a final transcript once the audio is finished.

**Why this priority**: This is the end-to-end core of the project. Without it nothing else has value; with only this, the learning goal (streaming call + Spanish recognition) is already demonstrable.

**Independent Test**: Start the service, run the client on a short Spanish audio file, and confirm the client prints at least one transcript marked final whose text matches what was spoken.

**Acceptance Scenarios**:

1. **Given** the service is running and its model is loaded, **When** the client streams a Spanish audio file in multiple chunks, **Then** the service returns transcript messages and a last message marked as final containing the full recognized text.
2. **Given** a 10-second audio file and a configured chunk size, **When** the client sends it, **Then** the audio is delivered as multiple progressive chunks within one call rather than as a single upload.
3. **Given** the client is run, **When** it starts, **Then** it does not load any speech model itself; all recognition happens in the service.

---

### User Story 2 - Receive partial results while audio is still arriving (Priority: P2)

While audio is still being sent, the developer sees intermediate transcripts that are clearly labeled as partial, followed by a final one when the stream ends. Audio from earlier chunks is retained so each result reflects everything heard so far, not just the latest chunk.

**Why this priority**: Demonstrates the value of bidirectional streaming and honest buffering behavior, but the system is still useful with only a final result.

**Independent Test**: Stream a multi-second Spanish file in several chunks and verify that results arrive before the stream ends, that they are labeled partial, and that the final one is labeled final and covers the whole utterance.

**Acceptance Scenarios**:

1. **Given** audio is still being streamed, **When** the service has enough audio to produce a result, **Then** it returns a transcript labeled partial without waiting for the stream to end.
2. **Given** the client has finished sending, **When** the service completes processing, **Then** it returns exactly one transcript labeled final.
3. **Given** the recognition approach's streaming mode only approximates offline recognition, **When** partial results are produced, **Then** they may be revised as more audio arrives, and this limitation is documented rather than hidden.

---

### User Story 3 - See latency and chunk metrics (Priority: P2)

After a run, the developer sees a report of how fast the system was: time to first transcript, total processing time, real-time factor, number of chunks, chunk duration, and audio duration.

**Why this priority**: Observing latency is a stated learning goal, but it depends on Story 1 working.

**Independent Test**: Run the client on a file of known length and verify the report shows all listed metrics with plausible values (e.g., audio duration matches the file length, chunk count matches length divided by chunk size).

**Acceptance Scenarios**:

1. **Given** a completed run, **When** the client finishes, **Then** it reports time to first transcript, total processing time, real-time factor (processing time ÷ audio duration), chunk count, chunk duration, and audio duration.
2. **Given** the service handles a request, **When** it starts, receives chunks, emits transcripts, finishes, or fails, **Then** each of these events is recorded in lightweight logs.

---

### User Story 4 - Clear errors for bad input (Priority: P3)

When the developer sends audio the service cannot interpret (unsupported sample rate, channel count, encoding, or corrupted data), they get a clear, categorized error rather than a crash, a hang, or an internal stack trace.

**Why this priority**: Improves robustness and teaches proper error semantics, but the happy path comes first.

**Independent Test**: Send streams with an unsupported sample rate, an unsupported channel count, and corrupted bytes; confirm each is rejected with an appropriate error category and a readable message, and that the service keeps running.

**Acceptance Scenarios**:

1. **Given** a stream declaring an unsupported sample rate, channel count, or encoding, **When** the service receives it, **Then** it rejects the request as an invalid argument with a message naming the problem.
2. **Given** corrupted or misaligned audio data, **When** the service receives it, **Then** it reports an error without exposing internal stack traces, and remains available for the next request.
3. **Given** the model is not ready or an unexpected internal failure occurs, **When** a request arrives, **Then** the service returns a precondition-failed, internal, or unavailable error as appropriate.

---

### User Story 5 - Configure and shut down cleanly (Priority: P3)

The developer can change model identifier, host, port, expected sample rate, channels, and chunk size without editing code. The model is loaded once at startup, and stopping the service ends open streams and releases resources cleanly.

**Why this priority**: Supports local usability and lifecycle correctness; not required to demonstrate core behavior.

**Independent Test**: Start the service with a non-default port and verify the client connects only when using that port; send several requests and confirm the model is loaded only once; stop the service during an active stream and confirm it exits cleanly.

**Acceptance Scenarios**:

1. **Given** configuration values are supplied via environment or command-line options, **When** the service and client start, **Then** they use those values instead of defaults.
2. **Given** multiple consecutive requests, **When** each is handled, **Then** the model is not reloaded per request.
3. **Given** the service receives a shutdown signal, **When** streams are active, **Then** it terminates without leaving open connections or inconsistent state.

---

### Edge Cases

- The stream ends without any audio chunks (empty stream): the service responds with a clear error or an empty final transcript, never hangs.
- The stream is cut mid-way by the client: the service releases that stream's buffered audio and keeps serving others.
- Audio is shorter than one chunk: a single chunk still yields a final transcript.
- Audio contains silence or non-Spanish speech: the service returns whatever text is recognized (possibly empty) as a final result without error.
- A chunk boundary falls in the middle of a sample: the service handles it consistently or rejects it clearly.
- Metadata is missing or changes mid-stream: the service rejects the stream as invalid.
- Two clients stream at once: each stream's audio buffer remains isolated from the other's.
- Very long audio: a stream longer than a configurable maximum (default 300 s) is rejected with a resource-exhausted error.
- A second stream arrives while another is being processed: it waits up to a configurable time (default 30 s), then is rejected as unavailable.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The service MUST transcribe Spanish speech using the Parakeet TDT 0.6B v3 model (`mlx-community/parakeet-tdt-0.6b-v3`) running locally on Apple Silicon.
- **FR-002**: The service MUST own the model; the client MUST NOT load or depend on any speech recognition model or library.
- **FR-003**: The service MUST expose a single speech service with a transcribe operation that accepts a stream of audio chunks and returns a stream of transcripts within one call (bidirectional streaming).
- **FR-004**: The interface contract MUST be defined in a strongly typed, language-neutral schema file, with generated code reproducible from it and never edited by hand.
- **FR-005**: The client MUST split audio into chunks of a configurable size and send them progressively.
- **FR-006**: The stream MUST carry enough audio metadata (sample rate, channel count, sample encoding) for the service to interpret the audio correctly.
- **FR-007**: The service MUST buffer audio per stream and MUST NOT treat each chunk as an independent utterance.
- **FR-008**: The service MUST emit a partial transcript after every N chunks received (N configurable, default 1) while audio is arriving, and MUST label each transcript as partial or final.
- **FR-009**: The service MUST emit a final transcript after the client ends its stream.
- **FR-010**: The system MUST use the model library's streaming mode for partials (state kept per stream); the documentation MUST state that streaming uses an approximation of offline recognition (partials may be revised, the final may differ slightly), and logs and docs MUST NOT claim more than is performed. If streaming were unavailable, the fallback is re-processing the accumulated audio.
- **FR-011**: The client MUST report time to first transcript, total processing time, real-time factor (processing time ÷ audio duration), number of chunks, chunk duration, and audio duration, measured with a monotonic clock.
- **FR-012**: The service MUST log request start, chunk receipt, transcript emission, final result, latency, and errors in a lightweight form.
- **FR-013**: The service MUST reject unsupported sample rate, channel count, encoding, or corrupted audio with a clear message.
- **FR-014**: The service MUST use appropriate status categories (invalid argument, failed precondition, resource exhausted, internal, unavailable) and MUST NOT expose internal stack traces to clients.
- **FR-015**: Model identifier, host, port, expected sample rate, expected channels, chunk size, and partial-emission interval (chunks per partial) MUST be configurable (command-line options and/or environment variables) with sensible defaults (model `mlx-community/parakeet-tdt-0.6b-v3`, host `localhost`, port `50051`).
- **FR-016**: The model MUST be loaded once at service startup, before requests are accepted, not per request.
- **FR-017**: The service MUST shut down gracefully, ending active streams and releasing resources.
- **FR-018**: The project MUST be separated into contract, client, and server areas (with ASR logic isolated from the network layer), include automated tests for chunking/buffering and the streaming contract that do not require a model download, and a README covering why gRPC, why bidirectional streaming, the contract, buffering, Parakeet integration, latency measurement, and model limitations.
- **FR-019**: The design MUST NOT preclude adding transport security, authentication, authorization, or quotas later; none are required now.
- **FR-020**: The first version MUST NOT include containers, orchestration, cloud deployment, message brokers, caches, LLM, TTS, telephony, authentication, production deployment, distributed tracing, complex monitoring, or autoscaling.

### Key Entities

- **Audio Chunk**: One piece of the audio stream; carries raw audio bytes and, at least on the first chunk, the metadata (sample rate, channels, encoding) needed to interpret the stream.
- **Transcript**: A recognition result; carries the recognized text and whether it is partial or final.
- **Stream Session**: The state of one transcribe call: accumulated audio buffer, declared audio format, counters, and timing; isolated per call and discarded when the call ends.
- **Run Metrics**: The measurements reported for a run: time to first transcript, total processing time, real-time factor, chunk count, chunk duration, audio duration.
- **Runtime Configuration**: The adjustable settings (model identifier, host, port, sample rate, channels, chunk size).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A developer can start the service and obtain a final Spanish transcript for a sample audio file by running two commands (server, then client) on a single Apple Silicon Mac with no external infrastructure.
- **SC-002**: For clear Spanish speech, the final transcript contains the spoken content with only minor recognition errors, confirmed manually on at least one reference recording.
- **SC-003**: For an audio file longer than one chunk, the client sends 2 or more chunks in a single call and receives at least one partial transcript before sending completes, plus exactly one final transcript.
- **SC-004**: Every run reports all six metrics (time to first transcript, total processing time, real-time factor, chunk count, chunk duration, audio duration), and the reported chunk count equals the audio length divided by the chunk size (rounded up).
- **SC-005**: 100% of the invalid-input cases tested (unsupported sample rate, unsupported channels, unsupported encoding, corrupted data) are rejected with a categorized, human-readable error, and the service remains usable for the next request.
- **SC-006**: Across 5 consecutive requests, the model is loaded exactly once.
- **SC-007**: Stopping the service while a stream is active ends it within 5 seconds with no orphaned processes or hung connections.
- **SC-008**: The automated tests covering chunking, buffering, and the streaming contract pass without downloading the model.
- **SC-009**: A developer can use the README alone to explain the roles of remote procedure calls, the gRPC framework, the typed contract, the transport, bidirectional streaming, and the recognition model.

## Assumptions

- The user is a single developer running everything locally on one Apple Silicon Mac; no multi-user or network-exposed use.
- Input audio is Spanish; default audio format is 16 kHz, mono, 16-bit PCM (configurable), and other formats are rejected rather than converted.
- The client's v1 audio source is a WAV file; microphone input is a future extension that must not require contract changes.
- No production latency targets are set; metrics exist to observe behavior, not to gate acceptance.
- Partials come from the model library's streaming mode and may be revised; streams are processed one at a time (others wait, bounded), and stream length is capped (default 300 s).
- `scripts/record_wav.py` is a manual-testing helper for recording a WAV; it is not part of the service.
- Concurrent streams are supported for isolation of state but are not a performance goal.
- The model weights are downloaded on first use and cached locally; that download is outside the automated tests.
- Dependencies are kept minimal, and the project layout follows the one in the project constitution (`proto/`, `server/`, `client/`, `tests/`, `requirements.txt`, `README.md`, `.gitignore`).
- Future integrations (telephony, LLM, TTS) are out of scope and only influence keeping the contract and client/server split clean.
