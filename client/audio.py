"""WAV reading and chunking (stdlib only; the client never loads a speech model)."""
import wave
from typing import Iterator, Tuple


def read_wav(path: str) -> Tuple[bytes, int, int, int]:
    """Return (pcm_bytes, sample_rate, channels, sample_width_bytes)."""
    with wave.open(path, "rb") as w:
        return w.readframes(w.getnframes()), w.getframerate(), w.getnchannels(), w.getsampwidth()


def iter_chunks(pcm: bytes, sample_rate: int, channels: int, chunk_ms: int,
                sample_width: int = 2) -> Iterator[bytes]:
    """Yield frame-aligned chunks of about `chunk_ms` of audio; the last may be shorter."""
    if chunk_ms <= 0:
        raise ValueError("chunk_ms must be positive")
    frame_bytes = channels * sample_width
    frames_per_chunk = max(1, sample_rate * chunk_ms // 1000)
    step = frames_per_chunk * frame_bytes
    for i in range(0, len(pcm), step):
        yield pcm[i:i + step]
