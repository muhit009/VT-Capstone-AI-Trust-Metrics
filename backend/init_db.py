from database import engine, Base

# Import all models so SQLAlchemy's metadata registry is fully populated
# before create_all() is called. Without these imports, the tables are
# not registered and will not be created.
from models.db_models import User, Query, Answer, ConfidenceSignal, Evidence, Decision


def init_db():
    print(f"Connecting to database at {engine.url}...")
    try:
        Base.metadata.create_all(bind=engine)
        print("Database schema created successfully.")
    except Exception as e:
        print(f"Failed to initialize database: {e}")


if __name__ == "__main__":
    init_db()
    