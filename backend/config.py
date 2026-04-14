from pathlib import Path

# Chunking settings (token-based; 1 token ≈ 4 chars for English)
CHUNK_SIZE = 500       # tokens
CHUNK_OVERLAP = 50     # tokens
CHARS_PER_TOKEN = 4

# Derived character counts used by RecursiveCharacterTextSplitter
CHAR_CHUNK_SIZE = CHUNK_SIZE * CHARS_PER_TOKEN      # 2000
CHAR_CHUNK_OVERLAP = CHUNK_OVERLAP * CHARS_PER_TOKEN  # 200

# Embedding settings
EMBEDDING_MODEL = "all-MiniLM-L6-v2"
EMBEDDING_BATCH_SIZE = 32

# ChromaDB settings
CHROMA_PERSIST_PATH = "./chroma_db"
CHROMA_COLLECTION_NAME = "document_embeddings"

# File storage
UPLOAD_DIR = Path("./uploads")
ALLOWED_EXTENSIONS = {".pdf", ".txt"}
MAX_FILE_SIZE_MB = 50
