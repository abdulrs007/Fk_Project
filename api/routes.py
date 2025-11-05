"""API route definitions."""
from typing import Optional, List
from datetime import datetime
import math
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pymongo import ASCENDING, DESCENDING
from loguru import logger

from api.auth import verify_api_key
from api.models import (
    BookResponse,
    PaginatedBooksResponse,
    ChangeResponse,
    PaginatedChangesResponse,
    HealthResponse,
    ErrorResponse
)
from utilities.database import db
from utilities.models import ChangeType


# Create router
router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Check API and database health status",
    tags=["System"]
)
async def health_check():
    """
    Health check endpoint - does not require authentication.

    Returns service status and basic stats.
    """
    try:
        total_books = await db.count_books()
        db_status = "connected"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        total_books = 0
        db_status = "disconnected"

    return HealthResponse(
        status="healthy" if db_status == "connected" else "unhealthy",
        timestamp=datetime.utcnow(),
        database=db_status,
        total_books=total_books
    )


@router.get(
    "/books",
    response_model=PaginatedBooksResponse,
    summary="List Books",
    description="Get paginated list of books with optional filtering and sorting",
    tags=["Books"],
    responses={
        403: {"model": ErrorResponse, "description": "Invalid API key"},
    }
)
async def list_books(
    page: int = Query(1, ge=1, description="Page number (starts at 1)"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page (max 100)"),
    category: Optional[str] = Query(None, description="Filter by category"),
    min_price: Optional[float] = Query(None, ge=0, description="Minimum price (inclusive)"),
    max_price: Optional[float] = Query(None, ge=0, description="Maximum price (inclusive)"),
    rating: Optional[str] = Query(None, description="Filter by rating (One, Two, Three, Four, Five)"),
    sort_by: str = Query(
        "crawl_timestamp",
        description="Sort field (name, price_incl_tax, rating, num_reviews, crawl_timestamp)"
    ),
    sort_order: str = Query("desc", description="Sort order (asc or desc)"),
    api_key: str = Depends(verify_api_key)
):
    """
    Get paginated list of books with filtering and sorting.

    **Query Parameters:**
    - **page**: Page number (default: 1)
    - **page_size**: Items per page (default: 50, max: 100)
    - **category**: Filter by category name
    - **min_price**: Minimum price filter
    - **max_price**: Maximum price filter
    - **rating**: Filter by rating (One, Two, Three, Four, Five)
    - **sort_by**: Field to sort by
    - **sort_order**: asc or desc

    **Authentication:**
    Requires API key in X-API-Key header.
    """
    # Validate sort_order
    if sort_order not in ["asc", "desc"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="sort_order must be 'asc' or 'desc'"
        )

    # Convert sort_order to pymongo constant
    sort_direction = ASCENDING if sort_order == "asc" else DESCENDING

    # Calculate skip
    skip = (page - 1) * page_size

    # Get books
    books_data = await db.get_all_books(
        skip=skip,
        limit=page_size,
        category=category,
        min_price=min_price,
        max_price=max_price,
        rating=rating,
        sort_by=sort_by,
        sort_order=sort_direction
    )

    # Build query for counting
    query = {}
    if category:
        query["category"] = category
    if min_price is not None or max_price is not None:
        query["price_incl_tax"] = {}
        if min_price is not None:
            query["price_incl_tax"]["$gte"] = min_price
        if max_price is not None:
            query["price_incl_tax"]["$lte"] = max_price
    if rating:
        query["rating"] = rating

    # Get total count
    total = await db.count_books(query)

    # Calculate total pages
    total_pages = math.ceil(total / page_size) if total > 0 else 0

    # Convert to response models
    books_response = [
        BookResponse(
            id=book["_id"],
            name=book["name"],
            description=book.get("description"),
            category=book["category"],
            price_excl_tax=book["price_excl_tax"],
            price_incl_tax=book["price_incl_tax"],
            availability=book["availability"],
            num_available=book["num_available"],
            num_reviews=book["num_reviews"],
            rating=book["rating"],
            image_url=book["image_url"],
            source_url=book["source_url"],
            crawl_timestamp=book["crawl_timestamp"]
        )
        for book in books_data
    ]

    return PaginatedBooksResponse(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        books=books_response
    )


@router.get(
    "/books/{book_id}",
    response_model=BookResponse,
    summary="Get Book Details",
    description="Get detailed information about a specific book",
    tags=["Books"],
    responses={
        403: {"model": ErrorResponse, "description": "Invalid API key"},
        404: {"model": ErrorResponse, "description": "Book not found"},
    }
)
async def get_book(
    book_id: str,
    api_key: str = Depends(verify_api_key)
):
    """
    Get detailed information about a specific book by ID.

    **Path Parameters:**
    - **book_id**: MongoDB ObjectId of the book

    **Authentication:**
    Requires API key in X-API-Key header.
    """
    from bson import ObjectId
    from bson.errors import InvalidId

    try:
        # Validate ObjectId
        obj_id = ObjectId(book_id)
    except InvalidId:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid book ID format"
        )

    # Get book from database
    book_data = await db.books.find_one({"_id": obj_id})

    if not book_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Book with ID {book_id} not found"
        )

    # Convert to response model
    return BookResponse(
        id=str(book_data["_id"]),
        name=book_data["name"],
        description=book_data.get("description"),
        category=book_data["category"],
        price_excl_tax=book_data["price_excl_tax"],
        price_incl_tax=book_data["price_incl_tax"],
        availability=book_data["availability"],
        num_available=book_data["num_available"],
        num_reviews=book_data["num_reviews"],
        rating=book_data["rating"],
        image_url=book_data["image_url"],
        source_url=book_data["source_url"],
        crawl_timestamp=book_data["crawl_timestamp"]
    )


@router.get(
    "/changes",
    response_model=PaginatedChangesResponse,
    summary="List Changes",
    description="Get recent changes (new books, price changes, availability changes)",
    tags=["Changes"],
    responses={
        403: {"model": ErrorResponse, "description": "Invalid API key"},
    }
)
async def list_changes(
    page: int = Query(1, ge=1, description="Page number (starts at 1)"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page (max 100)"),
    change_type: Optional[str] = Query(
        None,
        description="Filter by change type (new_book, price_change, availability_change, content_change)"
    ),
    api_key: str = Depends(verify_api_key)
):
    """
    Get recent changes with pagination.

    **Query Parameters:**
    - **page**: Page number (default: 1)
    - **page_size**: Items per page (default: 50, max: 100)
    - **change_type**: Filter by type of change

    **Authentication:**
    Requires API key in X-API-Key header.
    """
    # Validate change_type if provided
    if change_type:
        valid_types = ["new_book", "price_change", "availability_change", "content_change", "deleted"]
        if change_type not in valid_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid change_type. Must be one of: {', '.join(valid_types)}"
            )

    # Calculate skip
    skip = (page - 1) * page_size

    # Get changes from database
    query = {}
    if change_type:
        query["change_type"] = change_type

    # Get total count
    total = await db.changelog.count_documents(query)

    # Get changes
    cursor = db.changelog.find(query).sort("change_timestamp", DESCENDING).skip(skip).limit(page_size)

    changes_data = []
    async for change in cursor:
        changes_data.append(change)

    # Calculate total pages
    total_pages = math.ceil(total / page_size) if total > 0 else 0

    # Convert to response models
    changes_response = [
        ChangeResponse(
            id=str(change["_id"]),
            book_id=change["book_id"],
            book_name=change["book_name"],
            change_type=change["change_type"],
            change_timestamp=change["change_timestamp"],
            old_value=change.get("old_value"),
            new_value=change.get("new_value"),
            description=change.get("description")
        )
        for change in changes_data
    ]

    return PaginatedChangesResponse(
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        changes=changes_response
    )


@router.get(
    "/categories",
    response_model=List[str],
    summary="List Categories",
    description="Get list of all book categories",
    tags=["Books"],
    responses={
        403: {"model": ErrorResponse, "description": "Invalid API key"},
    }
)
async def list_categories(api_key: str = Depends(verify_api_key)):
    """
    Get list of all unique book categories.

    **Authentication:**
    Requires API key in X-API-Key header.
    """
    categories = await db.books.distinct("category")
    return sorted(categories)