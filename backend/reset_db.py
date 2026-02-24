from database import engine, Base
from models import db_models

def reset_database():
    print("Warning: This will delete all logged data on the laptop!")
    try:
        # 1. Drop all existing tables
        Base.metadata.drop_all(bind=engine)
        print("Dropped all existing tables.")
        
        # 2. Create them fresh
        Base.metadata.create_all(bind=engine)
        print("Successfully recreated the schema!")
    except Exception as e:
        print(f"Error resetting database: {e}")

if __name__ == "__main__":
    reset_database()