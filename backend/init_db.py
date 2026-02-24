from database import engine, Base
# Import your models so SQLAlchemy knows they exist
from models.db_models import User, Query, Answer, ConfidenceSignal, Evidence, Decision 

def init_db():
    print(f"Connecting to {engine.url}...")
    try:
        # This command creates all tables defined in db_models.py
        Base.metadata.create_all(bind=engine)
        print("Successfully created the schema on the laptop database!")
    except Exception as e:
        print(f"Failed to connect: {e}")

if __name__ == "__main__":
    init_db()