import grpc
import pytest

import generated  # noqa: F401
import speech_pb2
import speech_pb2_grpc

from server.config import ServerSettings
from server.server import build_server
from tests.fakes import FakeEngine


@pytest.fixture
def make_server():
    started = []

    def _make(engine=None, **overrides):
        settings = ServerSettings(port=0, **overrides)
        server, port, service = build_server(engine if engine is not None else FakeEngine(), settings)
        server.start()
        channel = grpc.insecure_channel(f"localhost:{port}")
        started.append((server, channel))
        return speech_pb2_grpc.SpeechServiceStub(channel), service

    yield _make
    for server, channel in started:
        channel.close()
        server.stop(0)


def config(rate=16000, channels=1, encoding=speech_pb2.PCM_S16LE):
    return speech_pb2.AudioChunk(config=speech_pb2.AudioConfig(
        sample_rate_hz=rate, channels=channels, encoding=encoding))


def audio(n_samples=800):
    return speech_pb2.AudioChunk(audio=bytes(2 * n_samples))
