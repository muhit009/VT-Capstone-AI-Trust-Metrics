import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from chunking import chunk_document

SAMPLE_DOC = {
    "filename": "sample.pdf",
    "file_type": "pdf",
    "pages": [
        {"page_num": 1, "text": "This is the first page. " * 100},
        {"page_num": 2, "text": "This is the second page. " * 100},
    ],
    "full_text": "",
    "page_count": 2,
}


def test_chunks_are_created():
    chunks = chunk_document(SAMPLE_DOC)
    assert len(chunks) > 0


def test_chunk_has_required_metadata():
    chunks = chunk_document(SAMPLE_DOC)
    for chunk in chunks:
        assert "text" in chunk
        assert "source" in chunk
        assert "page_num" in chunk
        assert "chunk_index" in chunk


def test_chunk_source_matches_filename():
    chunks = chunk_document(SAMPLE_DOC)
    for chunk in chunks:
        assert chunk["source"] == "sample.pdf"


def test_chunk_indices_are_sequential():
    chunks = chunk_document(SAMPLE_DOC)
    for i, chunk in enumerate(chunks):
        assert chunk["chunk_index"] == i


def test_page_numbers_are_correct():
    chunks = chunk_document(SAMPLE_DOC)
    page_nums = {c["page_num"] for c in chunks}
    assert 1 in page_nums
    assert 2 in page_nums


def test_empty_page_is_skipped():
    doc = {
        "filename": "empty.pdf",
        "file_type": "pdf",
        "pages": [{"page_num": 1, "text": "   "}],
        "full_text": "",
        "page_count": 1,
    }
    chunks = chunk_document(doc)
    assert len(chunks) == 0


def test_chunk_text_not_empty():
    chunks = chunk_document(SAMPLE_DOC)
    for chunk in chunks:
        assert chunk["text"].strip() != ""
