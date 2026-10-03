# Research: Live Microphone Transcription

## 1. Capture library
- **Decision**: `sounddevice` with a `RawInputStream` (16 kHz, 1 channel, `int16`, `blocksize` = chunk-ms worth of frames).
- **Rationale**: Python's stdlib cannot capture audio. PortAudio gives a callback-based capture that delivers raw little-endian int16 bytes, which is exactly `PCM_S16LE`, so no conversion or numpy is needed. Already available in the project venv.
- **Alternatives**: `pyaudio` (harder macOS install, less maintained); `ffmpeg`/`sox` subprocess (extra system dependency, harder to test); `soundcard` (less common).

## 2. Delivering audio to the gRPC request stream
- **Decision**: The capture callback only puts bytes on a `queue.Queue`; the request generator pulls from it and yields `AudioChunk`s until a stop event is set and the queue is drained.
- **Rationale**: The callback runs in a real-time audio thread and must never block on the network; the queue decouples capture from sending, so slow transcription never drops audio (spec edge case).
- **Alternatives**: yield directly from callback (blocks audio thread); asyncio (needless complexity).

## 3. Stopping
- **Decision**: A daemon thread waits on Enter from stdin and sets the stop event; `KeyboardInterrupt` does the same. Both lead to: stop stream, drain queue, close request stream, await final transcript, release device.
- **Rationale**: Enter does not fight the live-line rendering. Using the user's recommended default for the stop action (see Assumptions in spec) since the second clarification question was not answered.

## 4. Live-line display (clarified)
- **Decision**: Partial = `\r` + clear-line escape + `[partial] text` written without newline; final = clear line, print `[final] text` with newline.
- **Rationale**: Matches the clarified requirement FR-004; a single running transcript, final persisted.

## 5. Error handling
- **Decision**: Device-open failures (`sounddevice.PortAudioError`, no input devices, permission denied) are caught before any server call -> `error:` on stderr, exit 2. `grpc.RpcError` mid-session -> stop capture, `error:` message, exit 1, same as WAV mode.
- **Rationale**: Satisfies FR-007 and SC-004/005; reuses existing exit-code conventions.

## 6. Metrics in live mode
- **Decision**: Reuse `RunMetrics`: audio duration = bytes captured / byte rate; `t0` = first chunk sent. Additionally print "time from stop to final transcript".
- **Rationale**: For live use, post-stop wait is the latency the user feels; total processing includes speaking time so RTF is less meaningful, noted in README.

## 7. Testing without hardware
- **Decision**: Mic source is an injectable iterator of PCM chunks; tests feed a fake source and use the existing in-process server with the fake engine. `sounddevice` is imported only inside the real source.
- **Rationale**: Keeps `pytest` model-free and device-free (constitution quality gates).
