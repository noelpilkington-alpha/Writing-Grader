"""API key authentication."""

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

from .database import validate_api_key

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(api_key: str = Security(API_KEY_HEADER)) -> dict:
    """Dependency that validates the API key from the X-API-Key header."""
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key. Include X-API-Key header.")
    key_info = validate_api_key(api_key)
    if not key_info:
        raise HTTPException(status_code=403, detail="Invalid or inactive API key.")
    return key_info
