"""API request/response models."""
from typing import Optional, List, Any
from pydantic import BaseModel, Field
from datetime import datetime


class BookResponse(BaseModel):
    """Response model for a single book."""
    id: str = Field(..., description="Book ID")
    name: str
    description: Optional[str]
    category: str
    price_excl_tax: float
    price_incl_tax: float
    availability: str
    num_available: int
    num_reviews: int
    rating: str
    image_url: str
    source_url: str
    crawl_timestamp: datetime

    class Config:
        json_schema_extra = {
            "example": {
                "id": "507f1f77bcf86cd799439011",
                "name": "A Light in the Attic",
                "description": "It's hard to imagine...",
                "category": "Poetry",
                "price_excl_tax": 51.77,
                "price_incl_tax": 51.77,
                "availability": "In stock (22 available)",
                "num_available": 22,
                "num_reviews": 0,
                "rating": "Three",
                "image_url": "https://books.toscrape.com/media/cache/...",
                "source_url": "https://books.toscrape.com/catalogue/...",
                "crawl_timestamp": "2025-11-05T10:00:00Z"
            }
        }


class PaginatedBooksResponse(BaseModel):
    """Paginated response for book list."""
    total: int = Field(..., description="Total number of books matching query")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of items per page")
    total_pages: int = Field(..., description="Total number of pages")
    books: List[BookResponse] = Field(..., description="List of books")

    class Config:
        json_schema_extra = {
            "example": {
                "total": 1000,
                "page": 1,
                "page_size": 50,
                "total_pages": 20,
                "books": []
            }
        }


class ChangeResponse(BaseModel):
    """Response model for a change log entry."""
    id: str
    book_id: str
    book_name: str
    change_type: str
    change_timestamp: datetime
    old_value: Optional[dict]
    new_value: Optional[dict]
    description: Optional[str]

    class Config:
        json_schema_extra = {
            "example": {
                "id": "507f1f77bcf86cd799439012",
                "book_id": "507f1f77bcf86cd799439011",
                "book_name": "A Light in the Attic",
                "change_type": "price_change",
                "change_timestamp": "2025-11-05T10:00:00Z",
                "old_value": {"price_incl_tax": 51.77},
                "new_value": {"price_incl_tax": 45.99},
                "description": "Price decreased from £51.77 to £45.99"
            }
        }


class PaginatedChangesResponse(BaseModel):
    """Paginated response for changes list."""
    total: int
    page: int
    page_size: int
    total_pages: int
    changes: List[ChangeResponse]


class ErrorResponse(BaseModel):
    """Error response model."""
    detail: str = Field(..., description="Error message")

    class Config:
        json_schema_extra = {
            "example": {
                "detail": "Book not found"
            }
        }


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(..., description="Service status")
    timestamp: datetime = Field(..., description="Current server time")
    database: str = Field(..., description="Database connection status")
    total_books: int = Field(..., description="Total books in database")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "timestamp": "2025-11-05T10:00:00Z",
                "database": "connected",
                "total_books": 1000
            }
        }