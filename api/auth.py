"""API Key authentication for FastAPI."""
from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader
from loguru import logger

from utilities.config import settings


# Define API key header
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """
    Verify API key from request header.

    **How it works:**
    - Client sends API key in 'X-API-Key' header
    - We compare it with the configured API key
    - If valid, allow request to proceed
    - If invalid, return 403 Forbidden

    Args:
        api_key: API key from request header

    Returns:
        The validated API key

    Raises:
        HTTPException: If API key is missing or invalid
    """
    if not api_key:
        logger.warning("API request without API key")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="API key is missing. Include 'X-API-Key' header."
        )

    if api_key != settings.api_key:
        logger.warning(f"Invalid API key attempted: {api_key[:8]}...")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key"
        )

    return api_key