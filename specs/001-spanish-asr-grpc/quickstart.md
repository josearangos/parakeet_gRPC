# Quickstart / Validation Guide

## Prerequisites
- Apple Silicon Mac, Python 3.13, a 16 kHz mono 16-bit Spanish WAV (e.g. `samples/es.wav`).

## Setup
```bash
python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
./scripts/gen_proto.sh          # generates speech_pb2*.py from proto/speech.proto
```

Record your own test file (optional, needs `pip install -r requirements-record.txt`):
```bash
python scripts/record_wav.py --seconds 10     # saves samples/es.wav (16 kHz mono 16-bit)
```

## Run
```bash
python -m server.server                      # terminal 1: loads model once, logs "ready"
python -m client.client samples/es.wav       # terminal 2
```
Optional: `GRPC_PORT=50052 python -m server.server`, `--chunk-ms 250` on the client.

## Expected outcome
- Client prints partial transcripts (marked partial) then one final transcript.
- Metrics block: time to first transcript, total processing time, RTF, chunk count, chunk duration, audio duration.

## Validation scenarios
1. **Happy path** (US1/US2): above; at least 2 chunks, ≥1 partial before sending completes, one final.
2. **Metrics** (US3): chunk count = ceil(audio_seconds / chunk seconds).
3. **Bad input** (US4): `--sample-rate 8000` or a corrupted file → `INVALID_ARGUMENT`, server stays up.
4. **Config/lifecycle** (US5): different port works; model loaded once across 5 runs (check server log); Ctrl-C during a stream exits within 5 s.
5. **Tests**: `pytest` (no model download).
