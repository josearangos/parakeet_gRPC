"""ASR layer. The only module that imports MLX / Parakeet (and only inside ParakeetEngine)."""
import threading
from concurrent.futures import ThreadPoolExecutor
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
    def __init__(self, transcriber, run, release):
        self._t = transcriber
        self._run = run
        self._release = release
        self._closed = False

    def add_audio(self, samples: np.ndarray) -> str:
        def work():
            import mlx.core as mx
            self._t.add_audio(mx.array(samples))
            return self._t.result.text
        return self._run(work)

    def finalize(self) -> str:
        return self._run(lambda: self._t.result.text)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._run(lambda: self._t.__exit__(None, None, None))
        finally:
            self._release()


class ParakeetEngine:
    """Owns the Parakeet model, loaded once.

    MLX streams are bound to the thread that created them, so the model is loaded and ALL inference runs on
    one dedicated worker thread (gRPC handler threads only submit work to it). Entering a streaming context
    also switches the shared model's encoder to local attention, so only one stream is processed at a time
    (others wait on `_stream_lock`).
    """

    def __init__(self, model_id: str):
        self.model_id = model_id
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mlx")
        self._stream_lock = threading.Lock()
        self._model = self._run(self._load)

    def _run(self, fn):
        return self._pool.submit(fn).result()

    def _load(self):
        from parakeet_mlx import from_pretrained
        return from_pretrained(self.model_id)

    def open_stream(self) -> StreamHandle:
        self._stream_lock.acquire()
        try:
            def work():
                t = self._model.transcribe_stream(
                    context_size=(256, 256), depth=1, keep_original_attention=False)
                t.__enter__()
                return t
            t = self._run(work)
        except BaseException:
            self._stream_lock.release()
            raise
        return _ParakeetStream(t, self._run, self._stream_lock.release)

    def close(self) -> None:
        self._pool.shutdown(wait=True)
