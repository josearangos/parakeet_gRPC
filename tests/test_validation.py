import grpc
import pytest

import speech_pb2
from tests.conftest import audio, config
from tests.fakes import FakeEngine


def code_of(stub, msgs):
    with pytest.raises(grpc.RpcError) as e:
        list(stub.Transcribe(iter(msgs)))
    return e.value


@pytest.mark.parametrize("msgs", [
    [],                                              # empty stream
    [audio()],                                       # missing config
    [config(rate=8000), audio()],                    # sample rate
    [config(channels=2), audio()],                   # channels
    [config(encoding=speech_pb2.ENCODING_UNSPECIFIED), audio()],
    [config(), speech_pb2.AudioChunk(audio=b"\0\0\0")],   # odd byte length
    [config(), audio(), config()],                   # config mid-stream
])
def test_invalid_argument(make_server, msgs):
    stub, _ = make_server()
    assert code_of(stub, msgs).code() == grpc.StatusCode.INVALID_ARGUMENT
    # server remains usable
    out = list(stub.Transcribe(iter([config(), audio()])))
    assert out[-1].is_final


def test_too_long_stream(make_server):
    stub, _ = make_server(max_stream_seconds=1)
    err = code_of(stub, [config()] + [audio(16000), audio(16000)])
    assert err.code() == grpc.StatusCode.RESOURCE_EXHAUSTED


def test_engine_failure_is_internal_without_traceback(make_server):
    stub, _ = make_server(FakeEngine(fail=True))
    err = code_of(stub, [config(), audio()])
    assert err.code() == grpc.StatusCode.INTERNAL
    assert "boom" not in err.details() and "secret" not in err.details()


def test_not_ready_is_failed_precondition(make_server):
    stub, service = make_server()
    service.ready = False
    assert code_of(stub, [config(), audio()]).code() == grpc.StatusCode.FAILED_PRECONDITION


def test_shutting_down_is_unavailable(make_server):
    stub, service = make_server()
    service.stopping.set()
    assert code_of(stub, [config(), audio()]).code() == grpc.StatusCode.UNAVAILABLE


def test_engine_busy_is_unavailable(make_server):
    from server.asr import EngineBusy

    class Busy(FakeEngine):
        def open_stream(self):
            raise EngineBusy("another stream is in progress")

    stub, _ = make_server(Busy())
    err = code_of(stub, [config(), audio()])
    assert err.code() == grpc.StatusCode.UNAVAILABLE
