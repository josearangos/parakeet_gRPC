# Quickstart: Live Microphone Transcription

## Prerequisites
- Feature 001 working (venv, `./scripts/gen_proto.sh`, server runs).
- `pip install -r requirements.txt` (adds `sounddevice`).
- macOS: allow Microphone access for your terminal app (System Settings > Privacy & Security > Microphone).

## Scenarios
1. **Happy path**: terminal 1 `python -m server.server`; terminal 2 `python -m client.client --mic`. Speak Spanish: a live line updates while you talk. Press Enter: `[final] ...` is printed and the metrics block follows. (SC-001..003)
2. **No server**: stop the server, run `--mic`: a clear `error:` message, clean exit, microphone released. (SC-004/005)
3. **No microphone / denied access**: revoke permission or unplug input: `error:` message, exit code 2, server never contacted.
4. **Ctrl+C mid-speech**: session ends cleanly with a final transcript or a clear message; no traceback.
5. **Regression**: `python -m client.client path/to.wav` and `pytest` behave as before. (SC-006)

## Automated (no hardware, no model)
`pytest tests/test_client_mic.py` - fake microphone source against the in-process server with the fake engine.

## Results (2026-10-03, MacBook Apple Silicon, built-in microphone)

| Scenario | Result |
|---|---|
| 1. Happy path (14-16 s Spanish speech, Enter to stop) | PASS. First transcript 0.20 s (SC-001); ~30 partials during 16 s speech (SC-002); final 0.3 s after the last chunk (SC-003). Found and fixed: long partials wrapped and stacked rows (T026). |
| 2. Server down | PASS. `error: UNAVAILABLE ... Connection refused`, exit 1, no traceback, process exits (mic released). |
| 3. No microphone | PASS (simulated: PortAudio reporting no input device). `error: cannot open the microphone ... Microphone permission` hint, exit 2, server never contacted. Real revocation of macOS permission was not exercised; silent-denial (device opens but yields silence) remains unverified. |
| 4. Ctrl+C mid-session | Initially FAIL: gRPC `ValueError` traceback. Fixed (T027); now exit 0, final transcript and metrics printed, no traceback, also when interrupted 2 s after start. |
| 5. Regression | PASS. WAV mode unchanged (final + metrics, RTF ~0.5); `pytest` 49 passed. |
