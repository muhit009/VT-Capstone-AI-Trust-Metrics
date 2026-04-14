import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

# Validate required env vars at startup — fail fast with a clear message
# rather than silently building a broken connection URL.
_REQUIRED = {
    "DB_IP":   "DB_IP (database server IP or hostname)",
    "DB_PORT": "DB_PORT (database port, e.g. 5432)",
    "DB_NAME": "DB_NAME (database name)",
    "DB_USER": "DB_USER (database username)",
    "DB_PASS": "DB_PASS (database password)",
}
_missing = [desc for var, desc in _REQUIRED.items() if not os.getenv(var)]
if _missing:
    raise EnvironmentError(
        "Missing required database environment variables:\n"
        + "\n".join(f"  - {d}" for d in _missing)
        + "\nSet these in your .env file before starting the server."
    )

DB_HOST = os.getenv("DB_IP")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")

SQLALCHEMY_DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"sslmode": "require"},
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        