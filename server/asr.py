"""ASR layer. The only module that imports MLX / Parakeet (and only inside ParakeetEngine)."""
import threading
from typing import Protocol

import numpy as np


class StreamHandle(Protocol):
    def add_audio(self, samples: np.ndarray) -> str:
        """Feed float32 mono samples in [-1, 1]; return the transcript so far."""

    def finalize(self) -> str:
        """Return the final transcript."""

    def close(self) -> None:
        """Release per-stream resources."""


class Engine(Protocol):
    def open_stream(self) -> StreamHandle: ...


class _ParakeetStream:
    def __init__(self, transcriber, release):
        self._t = transcriber
        self._release = release
        self._closed = False

    def add_audio(self, samples: np.ndarray) -> str:
        import mlx.core as mx
        self._t.add_audio(mx.array(samples))
        return self._t.result.text

    def finalize(self) -> str:
        return self._t.result.text

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._t.__exit__(None, None, None)
        finally:
            self._release()


class ParakeetEngine:
    """Owns the Parakeet model, loaded once. Uses the library's streaming context.

    Entering a streaming context switches the shared model's encoder to local attention, so
    only one stream is processed at a time (others wait on `_stream_lock`).
    """

    def __init__(self, model_id: str):
        from parakeet_mlx import from_pretrained
        self.model_id = model_id
        self._model = from_pretrained(model_id)
        self._stream_lock = threading.Lock()

    def open_stream(self) -> StreamHandle:
        self._stream_lock.acquire()
        try:
            t = self._model.transcribe_stream(
                context_size=(256, 256), depth=1, keep_original_attention=False)
            t.__enter__()
        except BaseException:
            self._stream_lock.release()
            raise
        return _ParakeetStream(t, self._stream_lock.release)
