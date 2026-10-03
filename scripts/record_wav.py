"""Record microphone audio to a WAV in the format the ASR server expects (16 kHz, mono, 16-bit PCM).

Usage:
    python scripts/record_wav.py                       # 8 s -> samples/es.wav
    python scripts/record_wav.py --seconds 12 --out samples/prueba.wav
    python scripts/record_wav.py --list-devices

Needs `pip install -r requirements-record.txt` (sounddevice). This is a helper for manual testing only;
the server and client do not depend on it.
"""
import argparse
import os
import sys
import time
import wave

SAMPLE_RATE = 16000
CHANNELS = 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--seconds", type=float, default=8.0, help="recording length (default 8)")
    p.add_argument("--out", default="samples/es.wav", help="output WAV path (default samples/es.wav)")
    p.add_argument("--device", default=None, help="input device index or name (see --list-devices)")
    p.add_argument("--list-devices", action="store_true")
    a = p.parse_args(argv)

    try:
        import sounddevice as sd
    except ImportError:
        print("error: sounddevice not installed. Run: pip install -r requirements-record.txt",
              file=sys.stderr)
        return 2

    if a.list_devices:
        print(sd.query_devices())
        return 0
    if a.seconds <= 0:
        print("error: --seconds must be positive", file=sys.stderr)
        return 2

    device = int(a.device) if a.device is not None and a.device.isdigit() else a.device

    print("Speak in Spanish after the countdown.")
    for n in (3, 2, 1):
        print(f"  {n}...", flush=True)
        time.sleep(1)
    print(f"Recording {a.seconds:g} s... (speak now)", flush=True)
    try:
        audio = sd.rec(int(a.seconds * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=CHANNELS,
                       dtype="int16", device=device)
        sd.wait()
    except Exception as e:  # PortAudio errors: no mic, permission denied, bad device
        print(f"error: could not record: {e}\n"
              "On macOS, allow microphone access for your terminal in System Settings > Privacy & Security.",
              file=sys.stderr)
        return 1

    peak = int(abs(audio).max())
    if peak < 200:
        print("warning: the recording is almost silent; check the microphone and permissions.",
              file=sys.stderr)

    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with wave.open(a.out, "wb") as w:
        w.setnchannels(CHANNELS)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        w.writeframes(audio.tobytes())
    print(f"Saved {a.out} ({a.seconds:g} s, {SAMPLE_RATE} Hz, mono, 16-bit PCM)")
    print(f"Next: python -m client.client {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
