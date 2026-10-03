# Feature Specification: Live Microphone Transcription

**Feature Branch**: `002-live-microphone-transcription`

**Created**: 2026-10-03

**Status**: Draft

**Input**: User description: "It adds another feature to activate the microphone and send real-time audio chunks to the server and display the transcription."

## Clarifications

### Session 2026-10-03

- Q: When a new partial transcript arrives, should it replace the previous text on the same terminal line or be printed as a new line? → A: Overwrite one live line with each partial; print the final transcript on its own permanent line
- Q: How should the user start microphone mode and stop recording? → A: `--mic` flag on the existing client; press Enter to stop (Ctrl+C also ends the session cleanly). Default taken from the recommended option; the question was not answered explicitly.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Speak and see live transcription (Priority: P1)

A user starts the client in microphone mode. The client begins capturing audio from the default input device, sends it to the existing transcription server in small consecutive pieces while the user is still speaking, and shows the transcription on screen as results arrive. The user stops capture (e.g., by pressing Enter or Ctrl+C), and a final transcript for the whole utterance is shown.

**Why this priority**: This is the whole feature: replacing the pre-recorded WAV source with live speech while reusing the same server and results display.

**Independent Test**: Start the server, run the client in microphone mode, speak a Spanish sentence, and observe partial transcripts appearing before speech ends and a final transcript after stopping.

**Acceptance Scenarios**:

1. **Given** the server is running and a microphone is available, **When** the user starts microphone mode and speaks in Spanish, **Then** partial transcripts appear on screen while they are still speaking.
2. **Given** the user is speaking in microphone mode, **When** the user stops capture, **Then** the microphone is released and a final transcript is displayed, clearly distinguished from partial ones.
3. **Given** microphone mode is active, **When** transcripts update, **Then** the displayed text reflects the full speech so far rather than isolated fragments.

---

### User Story 2 - Clear feedback and graceful failure (Priority: P2)

The user always knows whether the system is listening, and problems (no microphone, permission denied, server unreachable, server dropping mid-session) produce a readable message and a clean exit instead of a crash or silent hang.

**Why this priority**: Live capture adds failure modes the file-based flow never had; unclear behavior makes the feature feel broken.

**Independent Test**: Run microphone mode with no input device or with the server stopped, and confirm a clear message and clean exit.

**Acceptance Scenarios**:

1. **Given** microphone mode starts, **When** capture begins, **Then** the user sees an indication that the system is listening and how to stop.
2. **Given** no microphone is available or access is denied, **When** the user starts microphone mode, **Then** a clear error is shown and the program exits without contacting the server.
3. **Given** the server becomes unreachable during capture, **When** the connection is lost, **Then** the microphone is released and a clear error is shown.

---

### User Story 3 - Latency metrics for live sessions (Priority: P3)

After a microphone session ends, the user sees the same style of latency summary as in file mode (audio duration, time to first transcript, total processing time, chunk count), so live and file behavior can be compared.

**Why this priority**: Measuring latency is a core goal of the project, but the feature is usable without it.

**Independent Test**: Complete one microphone session and verify a metrics summary is printed.

**Acceptance Scenarios**:

1. **Given** a finished microphone session, **When** the final transcript is shown, **Then** a metrics summary including time to first transcript is printed.

---

### Edge Cases

- User stops capture immediately or speaks nothing: the session ends cleanly with an empty or no-speech final result and no error.
- Long continuous speech: the session respects the server's existing maximum stream duration and tells the user when the limit ends the session.
- Background noise or silence only: no crash; transcripts may be empty.
- Microphone native format differs from the expected audio format: audio is delivered to the server in the format it expects.
- Transcription is slower than speech: capture continues without dropping audio, and results catch up.
- User interrupts (Ctrl+C) at any point: microphone is released and the terminal is left in a clean state.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The client MUST offer a microphone mode, selectable at launch with a `--mic` flag, alongside the existing WAV file mode.
- **FR-002**: In microphone mode, the system MUST capture audio from the default input device and send it to the server continuously in short consecutive chunks while capture is active.
- **FR-003**: The audio MUST be sent in the format the server expects (16 kHz, mono, 16-bit PCM by default), with configurable chunk duration.
- **FR-004**: The system MUST display partial transcripts as they arrive during capture by overwriting a single live line with each new partial, and MUST print the final transcript after capture stops on its own permanent line, clearly marked as final.
- **FR-005**: The user MUST be able to stop capture by pressing Enter (or Ctrl+C), after which the system closes the stream, awaits the final transcript, and releases the microphone.
- **FR-006**: The system MUST show when it is listening and how to stop.
- **FR-007**: The system MUST report a clear error and exit cleanly when no input device is available, access is denied, or the server is unreachable or disconnects.
- **FR-008**: The server's contract and behavior MUST remain unchanged; microphone mode is a new audio source for the existing service.
- **FR-009**: The system MUST report session metrics (audio duration, time to first transcript, total processing time, chunk count) for microphone sessions.
- **FR-010**: The model-inference and audio-capture responsibilities MUST stay separated: the client captures and displays; the server alone performs transcription.
- **FR-011**: Existing WAV file mode MUST continue to work unchanged.

### Key Entities

- **Live audio session**: One microphone capture from start to stop, producing an ordered sequence of audio chunks and the transcripts returned for it.
- **Audio chunk**: A short, fixed-duration piece of captured audio in the agreed format.
- **Transcript update**: Text returned by the server, marked partial or final, reflecting speech so far.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can go from launching microphone mode to seeing their first partial transcript in under 3 seconds of starting to speak (on the reference Apple Silicon machine).
- **SC-002**: For a 10-second spoken Spanish sentence, at least 3 partial transcripts appear before the user stops speaking.
- **SC-003**: After stopping capture, the final transcript appears within 3 seconds for utterances up to 30 seconds.
- **SC-004**: In 100% of runs with no microphone, denied access, or an unreachable server, the user sees an actionable error message and the program exits without hanging.
- **SC-005**: After any exit (normal stop, Ctrl+C, or error), the microphone is no longer in use.
- **SC-006**: The existing file-based flow and its tests pass unchanged.

## Assumptions

- Users run the client on the same Apple Silicon machine (macOS) as the project, with a working built-in or external microphone and system microphone permission granted to the terminal.
- Only the system default input device is used; device selection is out of scope.
- The feature is terminal-based: transcripts are displayed in the terminal, no graphical or web interface.
- Spanish is the only supported language, as in the existing service.
- Transcription uses the existing server's re-transcribe-the-buffer approach, so partial transcripts may revise earlier text; true incremental decoding is not claimed.
- No audio or transcripts are saved to disk unless the user explicitly asks (out of scope here).
- Voice-activity detection, noise suppression, multi-speaker handling, and telephony are out of scope.
- The server is already running and reachable at the configured host and port.
