import socket
import time

import grpc
import pytest

from client import client
from client.mic import MicError
from server.config import ServerSettings
from server.server import build_server
from tests.fakes import FakeEngine

CHUNK = bytes(2 * 800)


class FakeMic:
    """Stands in for MicSource: yields a fixed list of PCM chunks."""

    def __init__(self, n=4):
        self.n = n
        self.closed = False

    def chunks(self):
        for _ in range(self.n):
            yield CHUNK

    def stop(self):
        pass

    def close(self):
        self.closed = True


@pytest.fixture
def live_server():
    server, port, _ = build_server(FakeEngine(), ServerSettings(port=0))
    server.start()
    yield port
    server.stop(0)


def use_mic(monkeypatch, fake):
    monkeypatch.setattr(client, "open_mic", lambda chunk_ms: fake)


def test_live_chunks_in_partials_then_one_final(monkeypatch, live_server, capsys):
    fake = FakeMic(4)
    use_mic(monkeypatch, fake)
    assert client.main(["--mic", "--port", str(live_server)]) == 0
    out = capsys.readouterr().out
    assert out.count("[final]") == 1
    assert "[partial]" in out
    assert "palabra1 palabra2 palabra3 palabra4" in out
    assert fake.closed


def test_display_overwrites_partials_and_final_on_own_line(monkeypatch, live_server, capsys):
    use_mic(monkeypatch, FakeMic(3))
    client.main(["--mic", "--port", str(live_server)])
    out = capsys.readouterr().out
    assert "\r\x1b[2K[partial] palabra1" in out
    partial_part = out.split("[final]")[0]
    assert "\n" not in partial_part.replace("\r\x1b[2K", "")  # no newline between partials
    assert out.split("[final]")[1].startswith(" palabra1 palabra2 palabra3\n")


def test_metrics_reported(monkeypatch, live_server, capsys):
    use_mic(monkeypatch, FakeMic(4))
    assert client.main(["--mic", "--port", str(live_server)]) == 0
    out = capsys.readouterr().out
    assert "--- metrics ---" in out
    assert "audio duration:           0.20 s" in out  # 4 x 800 samples @ 16 kHz
    assert "chunks:                   4 x 500 ms" in out
    assert "time from stop to final:" in out


def test_no_microphone_is_clean_error_without_contacting_server(monkeypatch, capsys):
    def boom(chunk_ms):
        raise MicError("cannot open the microphone: no input device")

    monkeypatch.setattr(client, "open_mic", boom)
    assert client.main(["--mic", "--port", "1"]) == 2
    err = capsys.readouterr().err
    assert "error:" in err and "Traceback" not in err


def test_unreachable_server_is_clean_error_and_releases_mic(monkeypatch, capsys):
    s = socket.socket()
    s.bind(("localhost", 0))
    port = s.getsockname()[1]
    s.close()  # nothing listens here
    fake = FakeMic(2)
    use_mic(monkeypatch, fake)
    assert client.main(["--mic", "--port", str(port)]) == 1
    err = capsys.readouterr().err
    assert "error: UNAVAILABLE" in err and "Traceback" not in err
    assert fake.closed


def test_usage_errors(capsys, tmp_path):
    assert client.main([]) == 2
    assert client.main([str(tmp_path / "a.wav"), "--mic"]) == 2
    assert "error:" in capsys.readouterr().err


def test_immediate_stop_zero_chunks_no_traceback(monkeypatch, live_server, capsys):
    use_mic(monkeypatch, FakeMic(0))
    client.main(["--mic", "--port", str(live_server)])
    assert "Traceback" not in capsys.readouterr().err


def test_mic_source_drains_queue_after_stop():
    from client.mic import MicSource
    src = MicSource(500)
    src._on_audio(CHUNK, 800, None, None)
    src._on_audio(CHUNK, 800, None, None)
    src.stop()
    assert list(src.chunks()) == [CHUNK, CHUNK]
    start = time.perf_counter()
    assert list(src.chunks()) == []
    assert time.perf_counter() - start < 1
