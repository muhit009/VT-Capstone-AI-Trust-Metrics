import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pathlib import Path
import chromadb

load_dotenv()

# Fetch variables from .env
DB_HOST = os.getenv("DB_IP")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")

# Update with your actual credentials
SQLALCHEMY_DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Dependency to get DB session in FastAPI routes
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def getChunksOfTextData(content: str):
    chunk_generator = RecursiveCharacterTextSplitter(
        separators=["\n\n", "\n", " "],
        chunk_size = 1000,
        chunk_overlap=20,
        is_separator_regex=False,
    )

    chunk_list = chunk_generator.create_documents(texts=[content])
    return chunk_list

def getEmbeddingsOfData():
    embedding_content = {
        'embedding': [],
        'ids': []
    }
    ids = 0
    folder_location = Path("data")
    model_embedding = SentenceTransformer("all-MiniLM-L6-v2")

    if folder_location is None:
        raise FileNotFoundError("Could not find folder")
    
    document_ingest = list(folder_location.glob("*.pdf"))

    for document in document_ingest:
        try:
            text = ""
            read_text = PdfReader(document)
            for page in read_text.pages:
                text += page.extract_text()
            pdf_chunk = getChunksOfTextData(text)
            for chunk in pdf_chunk:
                embedding_content['embedding'].append(model_embedding.encode(chunk).tolist())
                embedding_content['ids'].append(ids)
                ids += 1
        except Exception as e:
            print(f"Error during embedding process: {str(e)}")

    return embedding_content

def store_data_ingestion():
    chorma_client = chromadb.PersistentClient(path="./chroma_db")
    embeddings = getEmbeddingsOfData()
    #The setup for ChormaDB was assisted with Claude AI.
    chorma_client_collection = chorma_client.get_or_create_collection(
        name="embeddings_inclusion",
        metadata={"hnsw:space": "cosine"}
    )
    chorma_client_collection.add(
        embeddings=embeddings['embedding'],
        ids=embeddings['ids']
    )
    return chorma_client_collection

print(store_data_ingestion())
