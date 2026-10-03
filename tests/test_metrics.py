from client.metrics import RunMetrics, expected_chunk_count


def test_rtf():
    m = RunMetrics(0.5, 20.0, 10.0, 20, 0.5)
    assert m.rtf == 2.0
    assert "RTF" in m.report()


def test_chunk_count():
    assert expected_chunk_count(10, 0.5) == 20
    assert expected_chunk_count(10.2, 0.5) == 21
