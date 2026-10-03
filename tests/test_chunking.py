import pytest

from client.audio import iter_chunks

SR = 16000


def test_ten_seconds_at_500ms_is_20_chunks():
    pcm = bytes(SR * 2 * 10)
    chunks = list(iter_chunks(pcm, SR, 1, 500))
    assert len(chunks) == 20
    assert b"".join(chunks) == pcm


def test_remainder_chunk_is_shorter_and_aligned():
    pcm = bytes(SR * 2 * 1 + 6)  # 1 s + 3 samples
    chunks = list(iter_chunks(pcm, SR, 1, 500))
    assert len(chunks) == 3
    assert len(chunks[-1]) == 6
    assert all(len(c) % 2 == 0 for c in chunks)


def test_stereo_alignment():
    pcm = bytes(SR * 4)  # 1 s stereo
    assert all(len(c) % 4 == 0 for c in iter_chunks(pcm, SR, 2, 300))


def test_invalid_chunk_size():
    with pytest.raises(ValueError):
        list(iter_chunks(b"\0\0", SR, 1, 0))
