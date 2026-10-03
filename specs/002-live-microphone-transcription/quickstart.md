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
