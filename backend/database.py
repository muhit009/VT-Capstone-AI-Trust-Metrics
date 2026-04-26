import os
import socket
from sqlalchemy import create_engine, URL
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

def _resolve_host_addr(hostname: str) -> str | None:
    """
    Resolve hostname to a numeric IP for psycopg2's hostaddr= parameter.
    Tries IPv4 first; if the host is IPv6-only (common with Supabase), falls
    back to the IPv6 address.  hostaddr= must always be a numeric IP.
    Returns None if resolution fails entirely.
    """
    # Prefer IPv4 — works everywhere including Docker on Windows
    try:
        results = socket.getaddrinfo(hostname, None, socket.AF_INET)
        if results:
            return results[0][4][0]
    except socket.gaierror:
        pass

    # Fall back to IPv6 — Supabase hostnames are often IPv6-only
    try:
        results = socket.getaddrinfo(hostname, None, socket.AF_INET6)
        if results:
            return results[0][4][0]   # returns bare IPv6 address e.g. "2600:1f16:..."
    except socket.gaierror:
        pass

    return None


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

DB_HOST_ADDR = _resolve_host_addr(DB_HOST)

SQLALCHEMY_DATABASE_URL = URL.create(
    drivername="postgresql",
    username=DB_USER,
    password=DB_PASS,
    host=DB_HOST,
    port=int(DB_PORT),
    database=DB_NAME,
)

_connect_args: dict = {"sslmode": "require"}

if DB_HOST_ADDR:
    _connect_args["hostaddr"] = DB_HOST_ADDR   # numeric IP bypasses runtime DNS lookup

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args=_connect_args,
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
        