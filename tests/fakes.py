import numpy as np


class FakeStream:
    def __init__(self, fail=False):
        self.calls = 0
        self.samples = 0
        self.closed = False
        self.fail = fail

    def add_audio(self, samples: np.ndarray) -> str:
        if self.fail:
            raise RuntimeError("boom /secret/path.py line 42")
        self.calls += 1
        self.samples += len(samples)
        return " ".join(f"palabra{i}" for i in range(1, self.calls + 1))

    def finalize(self) -> str:
        return " ".join(f"palabra{i}" for i in range(1, self.calls + 1))

    def close(self) -> None:
        self.closed = True


class FakeEngine:
    instances = 0

    def __init__(self, fail=False):
        FakeEngine.instances += 1
        self.fail = fail
        self.streams = []

    def open_stream(self):
        s = FakeStream(self.fail)
        self.streams.append(s)
        return s
