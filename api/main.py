"""FastAPI application with rate limiting."""
import sys
from pathlib import Path
from contextlib import asynccontextmanager

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from loguru import logger

from utilities.config import settings
from utilities.database import db
from utilities.logger import setup_logger
from api.routes import router


# Create rate limiter
limiter = Limiter(key_func=get_remote_address, default_limits=[f"{settings.rate_limit_per_hour}/hour"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown.

    **Startup:**
    - Connect to MongoDB
    - Setup database indexes

    **Shutdown:**
    - Disconnect from MongoDB
    """
    # Startup
    logger.info("Starting up API server...")
    try:
        await db.connect()
        logger.info("Database connected successfully")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down API server...")
    await db.disconnect()
    logger.info("Database disconnected")


# Create FastAPI app
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description="""
    # Books Crawler API

    Production-grade API for accessing crawled book data from books.toscrape.com

    ## Features

    - **Authentication**: API key-based authentication
    - **Rate Limiting**: 100 requests per hour (configurable)
    - **Pagination**: All list endpoints support pagination
    - **Filtering**: Filter books by category, price, rating
    - **Sorting**: Sort results by various fields
    - **Change Tracking**: View history of price/availability changes

    ## Authentication

    All endpoints (except /health) require an API key in the `X-API-Key` header:

    ```
    X-API-Key: your-api-key-here
    ```

    Default API key: `dev-api-key-12345` (change in production!)

    ## Rate Limiting

    - Default: 100 requests per hour per IP address
    - Configurable via environment variables
    - Returns 429 Too Many Requests when limit exceeded

    ## Response Format

    All successful responses return JSON. Errors return:

    ```json
    {
        "detail": "Error message here"
    }
    ```
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    responses={
        429: {
            "description": "Too Many Requests - Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {"detail": "Rate limit exceeded: 100 per 1 hour"}
                }
            }
        }
    }
)

# Add rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Add CORS middleware (allow all origins for development)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include routers
app.include_router(router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
async def root():
    """Redirect to API docs."""
    return {
        "message": "Books Crawler API",
        "version": settings.api_version,
        "docs": "/docs",
        "health": "/api/v1/health"
    }


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler for uncaught errors."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"}
    )


if __name__ == "__main__":
    import uvicorn

    logger.info(f"Starting {settings.api_title} v{settings.api_version}")
    logger.info(f"API will be available at: http://{settings.api_host}:{settings.api_port}")
    logger.info(f"Documentation: http://{settings.api_host}:{settings.api_port}/docs")

    uvicorn.run(
        "api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,  # Auto-reload on code changes (disable in production)
        log_level=settings.log_level.lower()
    )