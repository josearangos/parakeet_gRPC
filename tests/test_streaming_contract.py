import threading

from tests.conftest import audio, config


def run(stub, msgs):
    return list(stub.Transcribe(iter(msgs)))


def test_chunks_in_transcripts_out_final_last(make_server):
    stub, _ = make_server()
    out = run(stub, [config()] + [audio() for _ in range(5)])
    assert len(out) >= 2
    assert [t.is_final for t in out].count(True) == 1
    assert out[-1].is_final
    assert out[-1].chunks_received == 5
    assert out[-1].text == "palabra1 palabra2 palabra3 palabra4 palabra5"


def test_partial_every_n_chunks(make_server):
    stub, _ = make_server(partial_every_n_chunks=2)
    out = run(stub, [config()] + [audio() for _ in range(6)])
    partials = [t for t in out if not t.is_final]
    assert [t.chunks_received for t in partials] == [2, 4, 6]
    assert [t.audio_seconds for t in partials] == sorted(t.audio_seconds for t in partials)


def test_partial_arrives_before_client_closes_stream(make_server):
    stub, _ = make_server()
    release = threading.Event()

    def reqs():
        yield config()
        yield audio()
        release.wait(5)  # stream stays open until a transcript is seen

    it = stub.Transcribe(reqs())
    first = next(it)
    assert not first.is_final
    release.set()
    rest = list(it)
    assert rest[-1].is_final


def test_streams_are_isolated(make_server):
    stub, _ = make_server()
    results = {}

    def go(name, n):
        results[name] = run(stub, [config()] + [audio() for _ in range(n)])

    ts = [threading.Thread(target=go, args=("a", 2)), threading.Thread(target=go, args=("b", 4))]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert results["a"][-1].chunks_received == 2
    assert results["b"][-1].chunks_received == 4


def test_handle_closed_after_stream(make_server):
    from tests.fakes import FakeEngine
    engine = FakeEngine()
    stub, _ = make_server(engine)
    run(stub, [config(), audio()])
    assert engine.streams[0].closed


def test_model_object_created_once_across_rpcs(make_server):
    from tests.fakes import FakeEngine
    FakeEngine.instances = 0
    stub, _ = make_server()
    for _ in range(5):
        run(stub, [config(), audio()])
    assert FakeEngine.instances == 1
