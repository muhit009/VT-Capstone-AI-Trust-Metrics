from database import engine, Base

# Explicit model imports required to populate Base.metadata before
# drop_all/create_all. Mirrors init_db.py intentionally.
from models.db_models import User, Query, Answer, ConfidenceSignal, Evidence, Decision


def reset_database():
    print("WARNING: This will permanently delete all data in the database.")
    confirm = input("Type 'yes' to continue: ").strip().lower()
    if confirm != "yes":
        print("Aborted.")
        return
    try:
        Base.metadata.drop_all(bind=engine)
        print("Dropped all existing tables.")
        Base.metadata.create_all(bind=engine)
        print("Database schema recreated successfully.")
    except Exception as e:
        print(f"Error resetting database: {e}")


if __name__ == "__main__":
    reset_database()
    