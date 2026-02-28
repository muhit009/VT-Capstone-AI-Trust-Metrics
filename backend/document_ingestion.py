import json
import chardet
import pdfplumber
from pathlib import Path
from typing import Dict, List
from fastapi import HTTPException
from config import UPLOAD_DIR, ALLOWED_EXTENSIONS, MAX_FILE_SIZE_MB

MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024

# Create upload directory structure on import
(UPLOAD_DIR / "pdfs").mkdir(parents=True, exist_ok=True)
(UPLOAD_DIR / "texts").mkdir(parents=True, exist_ok=True)
(UPLOAD_DIR / "extracted").mkdir(parents=True, exist_ok=True)


def validate_file(filename: str, content: bytes) -> None:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}"
        )
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="File is empty.")
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds maximum size of {MAX_FILE_SIZE_MB}MB."
        )


def extract_text_from_pdf(file_path: Path) -> Dict:
    pages: List[Dict] = []
    try:
        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                text = page.extract_text() or ""

                # Append table rows as pipe-separated lines
                tables = page.extract_tables()
                if tables:
                    for table in tables:
                        for row in table:
                            row_text = " | ".join(cell or "" for cell in row)
                            text += f"\n{row_text}"

                pages.append({"page_num": page_num, "text": text.strip()})
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"Failed to extract text from PDF: {str(e)}"
        )

    full_text = "\n\n".join(p["text"] for p in pages if p["text"])
    return {
        "filename": file_path.name,
        "file_type": "pdf",
        "pages": pages,
        "full_text": full_text,
        "page_count": len(pages),
    }


def extract_text_from_txt(file_path: Path) -> Dict:
    try:
        raw = file_path.read_bytes()
        detected = chardet.detect(raw)
        encoding = detected.get("encoding") or "utf-8"
        text = raw.decode(encoding, errors="replace")
    except Exception as e:
        raise HTTPException(
            status_code=422,
            detail=f"Failed to read text file: {str(e)}"
        )

    return {
        "filename": file_path.name,
        "file_type": "txt",
        "pages": [{"page_num": 1, "text": text}],
        "full_text": text,
        "page_count": 1,
    }


def ingest_file(filename: str, content: bytes) -> Dict:
    validate_file(filename, content)
    ext = Path(filename).suffix.lower()

    # Save original file
    if ext == ".pdf":
        file_path = UPLOAD_DIR / "pdfs" / filename
    else:
        file_path = UPLOAD_DIR / "texts" / filename
    file_path.write_bytes(content)

    # Extract text
    if ext == ".pdf":
        doc_data = extract_text_from_pdf(file_path)
    else:
        doc_data = extract_text_from_txt(file_path)

    # Persist extracted text as JSON
    extracted_path = UPLOAD_DIR / "extracted" / f"{Path(filename).stem}.json"
    extracted_path.write_text(json.dumps(doc_data, indent=2), encoding="utf-8")

    return doc_data
