"""
middleware/auth.py — API Key Authentication Dependency

How it works:
    FastAPI's Depends() system runs this function automatically before any
    endpoint that declares `_: str = Depends(require_api_key)`.

    The client must send the key in the Authorization header like this:
        Authorization: Bearer <your-api-key>

    If API_KEY is not set in .env (local dev), auth is disabled entirely
    and every request passes through. In production, set API_KEY and every
    request without the correct key gets a 401 before touching any logic.

Usage in a router:
    from middleware.auth import require_api_key

    @router.post("/query")
    async def submit_query(
        ...,
        _: str = Depends(require_api_key),   # enforces key, result unused
    ):
        ...
"""

from fastapi import Header, HTTPException, status
from config import API_KEY


async def require_api_key(authorization: str = Header(default=None)) -> str:
    """
    FastAPI dependency that validates the Authorization: Bearer <key> header.

    Returns the key string on success (typically ignored via _ = Depends(...)).
    Raises HTTP 401 if the key is missing or wrong.
    Skips validation entirely if API_KEY is not configured (dev mode).
    """
    # Dev mode: no API_KEY set in .env → let everything through
    if API_KEY is None:
        return "dev-mode-no-key-required"

    # Production: key must be present and correct
    if authorization is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header. Expected: Authorization: Bearer <api-key>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Header format must be "Bearer <key>"
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Expected: Authorization: Bearer <api-key>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1]
    if token != API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return token