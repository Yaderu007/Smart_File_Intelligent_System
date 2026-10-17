""" Tests for the hashing functionality. """

import hashlib
import pytest

from src.scanner.hashing import hash_file


def test_hash_matches_direct_sha256(tmp_path):
    file_path = tmp_path / "data.bin"
    content = b"some file content" * 1000
    file_path.write_bytes(content)

    expected = hashlib.sha256(content).hexdigest()
    assert hash_file(file_path) == expected


def test_identical_content_produces_same_hash(tmp_path):
    file_a = tmp_path / "a.txt"
    file_b = tmp_path / "b.txt"
    file_a.write_text("identical content")
    file_b.write_text("identical content")

    assert hash_file(file_a) == hash_file(file_b)


def test_different_content_produces_different_hash(tmp_path):
    file_a = tmp_path / "a.txt"
    file_b = tmp_path / "b.txt"
    file_a.write_text("content one")
    file_b.write_text("content two")

    assert hash_file(file_a) != hash_file(file_b)


def test_hash_nonexistent_file_raises_oserror(tmp_path):
    missing = tmp_path / "ghost.txt"
    with pytest.raises(OSError):
        hash_file(missing)


def test_small_chunk_size_still_correct(tmp_path):
    file_path = tmp_path / "data.bin"
    content = b"x" * 10000
    file_path.write_bytes(content)

    expected = hashlib.sha256(content).hexdigest()
    assert hash_file(file_path, chunk_size=16) == expected