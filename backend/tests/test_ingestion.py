import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import HTTPException
from document_ingestion import validate_file, extract_text_from_txt


def test_validate_file_valid_pdf():
    validate_file("report.pdf", b"%PDF-1.4 content here")


def test_validate_file_valid_txt():
    validate_file("notes.txt", b"hello world")


def test_validate_file_unsupported_type():
    with pytest.raises(HTTPException) as exc:
        validate_file("doc.docx", b"content")
    assert exc.value.status_code == 400


def test_validate_file_empty_content():
    with pytest.raises(HTTPException) as exc:
        validate_file("empty.txt", b"")
    assert exc.value.status_code == 400


def test_validate_file_exceeds_size_limit():
    big_content = b"x" * (51 * 1024 * 1024)  # 51 MB
    with pytest.raises(HTTPException) as exc:
        validate_file("big.txt", big_content)
    assert exc.value.status_code == 400


def test_extract_text_from_txt_utf8(tmp_path):
    f = tmp_path / "sample.txt"
    f.write_text("Hello, world!", encoding="utf-8")
    result = extract_text_from_txt(f)
    assert result["full_text"] == "Hello, world!"
    assert result["file_type"] == "txt"
    assert result["page_count"] == 1
    assert result["pages"][0]["page_num"] == 1


def test_extract_text_from_txt_latin1(tmp_path):
    f = tmp_path / "latin.txt"
    f.write_bytes("Héllo wörld".encode("latin-1"))
    result = extract_text_from_txt(f)
    assert "llo" in result["full_text"]
    assert result["file_type"] == "txt"


def test_extract_text_from_txt_returns_filename(tmp_path):
    f = tmp_path / "myfile.txt"
    f.write_text("some text", encoding="utf-8")
    result = extract_text_from_txt(f)
    assert result["filename"] == "myfile.txt"
