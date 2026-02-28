from fastapi import APIRouter, UploadFile, File, HTTPException
from document_ingestion import ingest_file
from chunking import chunk_document
from embedding import embedding_service
from vector_store import vector_store

router = APIRouter(prefix="/v1/documents", tags=["documents"])


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    content = await file.read()
    doc_data = ingest_file(file.filename, content)
    chunks = chunk_document(doc_data)

    if not chunks:
        raise HTTPException(
            status_code=422,
            detail="No text could be extracted from the document."
        )

    embeddings = embedding_service.generate_embeddings(chunks)
    vector_store.add_documents(chunks, embeddings)

    return {
        "filename": file.filename,
        "file_type": doc_data["file_type"],
        "page_count": doc_data["page_count"],
        "chunk_count": len(chunks),
        "embedding_dim": len(embeddings[0]) if embeddings else 0,
        "status": "ingested",
    }


@router.get("/")
async def list_documents():
    sources = vector_store.list_documents()
    return {"documents": sources, "total": len(sources)}


@router.delete("/{filename}")
async def delete_document(filename: str):
    deleted = vector_store.delete_document(filename)
    if deleted == 0:
        raise HTTPException(
            status_code=404,
            detail=f"Document '{filename}' not found in the vector store."
        )
    return {"filename": filename, "chunks_deleted": deleted, "status": "deleted"}
