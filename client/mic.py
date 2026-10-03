"""Microphone capture source (audio capture only; no ASR library).

The audio callback only enqueues bytes; the request generator drains the queue, so a slow
network or slow transcription never blocks (or drops) capture.
"""
import queue
import sys
import threading
from typing import Iterator

SAMPLE_RATE = 16000
CHANNELS = 1
SAMPLE_WIDTH = 2  # int16


class MicError(Exception):
    """The microphone could not be opened; the message is safe to show the user."""


class MicSource:
    def __init__(self, chunk_ms: int):
        if chunk_ms <= 0:
            raise ValueError("chunk_ms must be positive")
        self.chunk_ms = chunk_ms
        self._queue: "queue.Queue[bytes]" = queue.Queue()
        self._stop = threading.Event()
        self._stream = None

    def start(self) -> None:
        try:
            import sounddevice as sd  # lazy: WAV mode and tests need no PortAudio
            sd.query_devices(kind="input")
            self._stream = sd.RawInputStream(
                samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="int16",
                blocksize=SAMPLE_RATE * self.chunk_ms // 1000, callback=self._on_audio)
            self._stream.start()
        except Exception as e:  # PortAudioError, ValueError (no device), ImportError, OSError
            self.close()
            raise MicError(f"cannot open the microphone: {e}. Check that an input device is "
                           "connected and that this terminal has Microphone permission "
                           "(macOS: System Settings > Privacy & Security > Microphone)") from e

    def _on_audio(self, indata, frames, time_info, status) -> None:
        self._queue.put(bytes(indata))

    def chunks(self) -> Iterator[bytes]:
        """Yield captured chunks until stop() is called and the queue is drained."""
        while True:
            try:
                yield self._queue.get(timeout=0.1)
            except queue.Empty:
                if self._stop.is_set():
                    return

    def stop(self) -> None:
        self._stop.set()

    def close(self) -> None:
        self._stop.set()
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None


def open_mic(chunk_ms: int) -> MicSource:
    src = MicSource(chunk_ms)
    src.start()
    return src


def stop_on_enter(source) -> None:
    """Stop `source` when the user presses Enter (daemon thread; only meaningful on a terminal)."""
    def wait():
        try:
            sys.stdin.readline()
        except Exception:
            return
        source.stop()
    threading.Thread(target=wait, daemon=True).start()
