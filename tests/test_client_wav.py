import wave

from client import client


def test_garbage_file_is_a_clean_error(tmp_path, capsys):
    f = tmp_path / "bad.wav"
    f.write_bytes(b"this is not a wav file")
    assert client.main([str(f)]) == 2
    err = capsys.readouterr().err
    assert "cannot read" in err and "Traceback" not in err


def test_missing_file_is_a_clean_error(tmp_path, capsys):
    assert client.main([str(tmp_path / "nope.wav")]) == 2
    assert "error:" in capsys.readouterr().err


def test_empty_audio_is_a_clean_error(tmp_path, capsys):
    f = tmp_path / "empty.wav"
    with wave.open(str(f), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
    assert client.main([str(f)]) == 2
    assert "no audio" in capsys.readouterr().err


def test_8bit_wav_is_rejected(tmp_path, capsys):
    f = tmp_path / "eight.wav"
    with wave.open(str(f), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(1)
        w.setframerate(16000)
        w.writeframes(bytes(1600))
    assert client.main([str(f)]) == 2
    assert "16-bit" in capsys.readouterr().err
