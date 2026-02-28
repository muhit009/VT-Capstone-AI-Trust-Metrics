from typing import List, Dict
from langchain_text_splitters import RecursiveCharacterTextSplitter
from config import CHAR_CHUNK_SIZE, CHAR_CHUNK_OVERLAP


def chunk_document(doc_data: Dict) -> List[Dict]:
    """
    Split a document into chunks of ~500 tokens (2000 chars) with
    ~50-token (200-char) overlap. Returns one entry per chunk with
    metadata: source filename, page number, and global chunk index.
    """
    splitter = RecursiveCharacterTextSplitter(
        separators=["\n\n", "\n", ". ", " ", ""],
        chunk_size=CHAR_CHUNK_SIZE,
        chunk_overlap=CHAR_CHUNK_OVERLAP,
        is_separator_regex=False,
    )

    chunks: List[Dict] = []
    chunk_index = 0

    for page in doc_data["pages"]:
        page_text = page["text"]
        if not page_text.strip():
            continue

        page_chunks = splitter.create_documents([page_text])
        for chunk in page_chunks:
            chunks.append({
                "text": chunk.page_content,
                "source": doc_data["filename"],
                "page_num": page["page_num"],
                "chunk_index": chunk_index,
            })
            chunk_index += 1

    return chunks
