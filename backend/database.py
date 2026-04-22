import os
import socket
from sqlalchemy import create_engine, URL
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()


def _resolve_ipv4(hostname: str) -> str | None:
    """
    Resolve a hostname to its first IPv4 address, or return None on failure.

    Used so that psycopg2's hostaddr= connect arg forces the connection
    over IPv4 even when DNS returns an IPv6 address first (unreachable
    inside Docker on Windows).  hostaddr= must be a numeric IP — never a
    hostname — so we return None rather than the original hostname when
    resolution fails.
    """
    try:
        results = socket.getaddrinfo(hostname, None, socket.AF_INET)
        if results:
            return results[0][4][0]
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

# Resolve hostname → IPv4 so psycopg2 doesn't attempt the IPv6 address
# that Supabase DNS returns (unreachable from Docker on Windows).
# hostaddr= forces the TCP connection to a specific IP; host= is still
# used for SSL certificate name verification.
# Only inject hostaddr when we successfully resolved an IPv4 address —
# psycopg2 requires hostaddr to be a numeric IP, not a hostname.
DB_HOST_IPV4 = _resolve_ipv4(DB_HOST)

SQLALCHEMY_DATABASE_URL = URL.create(
    drivername="postgresql",
    username=DB_USER,
    password=DB_PASS,
    host=DB_HOST,
    port=int(DB_PORT),
    database=DB_NAME,
)

_connect_args: dict = {"sslmode": "require"}
if DB_HOST_IPV4:
    _connect_args["hostaddr"] = DB_HOST_IPV4   # force IPv4 when available

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
        