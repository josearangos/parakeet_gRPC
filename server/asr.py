"""ASR layer. The only module that imports MLX / Parakeet (and only inside ParakeetEngine)."""
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Protocol

import numpy as np


class EngineBusy(Exception):
    """Another stream holds the engine and the wait limit elapsed (or the server is stopping)."""


class StreamGate:
    """One-stream-at-a-time lock whose waiters give up after a timeout or when interrupted."""

    def __init__(self, wait_seconds: float):
        self._lock = threading.Lock()
        self._wait_seconds = wait_seconds
        self._interrupted = threading.Event()

    def acquire(self) -> None:
        deadline = time.monotonic() + self._wait_seconds
        while not self._lock.acquire(timeout=0.2):
            if self._interrupted.is_set():
                raise EngineBusy("server is shutting down")
            if time.monotonic() >= deadline:
                raise EngineBusy(f"another stream is in progress (waited {self._wait_seconds:g}s)")

    def release(self) -> None:
        self._lock.release()

    def interrupt(self) -> None:
        self._interrupted.set()


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
    (others wait on the gate, at most `wait_seconds`).
    """

    def __init__(self, model_id: str, wait_seconds: float = 30.0):
        self.model_id = model_id
        self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="mlx")
        self._gate = StreamGate(wait_seconds)
        self._model = self._run(self._load)

    def _run(self, fn):
        return self._pool.submit(fn).result()

    def _load(self):
        from parakeet_mlx import from_pretrained
        return from_pretrained(self.model_id)

    def open_stream(self) -> StreamHandle:
        self._gate.acquire()  # raises EngineBusy
        try:
            def work():
                t = self._model.transcribe_stream(
                    context_size=(256, 256), depth=1, keep_original_attention=False)
                t.__enter__()
                return t
            t = self._run(work)
        except BaseException:
            self._gate.release()
            raise
        return _ParakeetStream(t, self._run, self._gate.release)

    def interrupt(self) -> None:
        """Make waiting streams give up (called when the server starts shutting down)."""
        self._gate.interrupt()

    def close(self) -> None:
        self._pool.shutdown(wait=True)
