import hashlib, pytest
from src.scanner.hashing import hash_file

def test_hash_matches_direct_sha256(tmp_path):
    file_path = tmp_path / "data.bin"
    content = b"some file content" * 1000
    file_path.write_bytes(content)
    assert hash_file(file_path) == hashlib.sha256(content).hexdigest()

def test_identical_content_produces_same_hash(tmp_path):
    a, b = tmp_path / "a.txt", tmp_path / "b.txt"
    a.write_text("identical"); b.write_text("identical")
    assert hash_file(a) == hash_file(b)

def test_different_content_produces_different_hash(tmp_path):
    a, b = tmp_path / "a.txt", tmp_path / "b.txt"
    a.write_text("one"); b.write_text("two")
    assert hash_file(a) != hash_file(b)

def test_hash_nonexistent_file_raises_oserror(tmp_path):
    with pytest.raises(OSError):
        hash_file(tmp_path / "ghost.txt")
