from client.metrics import RunMetrics


def test_rtf():
    m = RunMetrics(0.5, 20.0, 10.0, 20, 0.5)
    assert m.rtf == 2.0
    assert "RTF" in m.report()
