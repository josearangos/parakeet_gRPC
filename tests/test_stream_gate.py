import threading
import time

import pytest

from server.asr import EngineBusy, StreamGate


def test_second_waiter_times_out():
    g = StreamGate(wait_seconds=0.3)
    g.acquire()
    t0 = time.monotonic()
    with pytest.raises(EngineBusy):
        g.acquire()
    assert 0.25 <= time.monotonic() - t0 < 1.5
    g.release()
    g.acquire()  # free again after release


def test_waiter_gets_gate_when_released_in_time():
    g = StreamGate(wait_seconds=3)
    g.acquire()
    threading.Timer(0.3, g.release).start()
    g.acquire()


def test_interrupt_wakes_waiters_quickly():
    g = StreamGate(wait_seconds=30)
    g.acquire()
    threading.Timer(0.3, g.interrupt).start()
    t0 = time.monotonic()
    with pytest.raises(EngineBusy):
        g.acquire()
    assert time.monotonic() - t0 < 2
