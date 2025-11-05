"""Pydantic models for data validation and MongoDB schema."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, HttpUrl, field_validator
from enum import Enum


class CrawlStatus(str, Enum):
    """Status of a crawl operation."""
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"


class BookRating(str, Enum):
    """Book rating enumeration."""
    ONE = "One"
    TWO = "Two"
    THREE = "Three"
    FOUR = "Four"
    FIVE = "Five"


class Book(BaseModel):
    """
    Book model representing a book from the e-commerce site.

    MongoDB will auto-generate _id field when inserted.
    """
    # Book data
    name: str = Field(..., description="Name of the book")
    description: Optional[str] = Field(None, description="Book description")
    category: str = Field(..., description="Book category")
    price_excl_tax: float = Field(..., description="Price excluding tax", ge=0)
    price_incl_tax: float = Field(..., description="Price including tax", ge=0)
    availability: str = Field(..., description="Availability status (e.g., 'In stock (22 available)')")
    num_available: int = Field(..., description="Number of items available", ge=0)
    num_reviews: int = Field(0, description="Number of reviews", ge=0)
    rating: BookRating = Field(..., description="Book rating (One to Five)")
    image_url: str = Field(..., description="URL of the book cover image")

    # Metadata - added by crawler
    source_url: str = Field(..., description="Original URL of the book page")
    crawl_timestamp: datetime = Field(default_factory=datetime.utcnow, description="When this book was crawled")
    crawl_status: CrawlStatus = Field(default=CrawlStatus.SUCCESS, description="Status of the crawl")
    raw_html: Optional[str] = Field(None, description="Raw HTML snapshot of the book page")
    content_hash: Optional[str] = Field(None, description="Hash of book content for change detection")

    # MongoDB _id will be auto-generated
    id: Optional[str] = Field(None, alias="_id", description="MongoDB document ID")

    class Config:
        """Pydantic configuration."""
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "name": "A Light in the Attic",
                "description": "It's hard to imagine a world without A Light in the Attic...",
                "category": "Poetry",
                "price_excl_tax": 51.77,
                "price_incl_tax": 51.77,
                "availability": "In stock (22 available)",
                "num_available": 22,
                "num_reviews": 0,
                "rating": "Three",
                "image_url": "https://books.toscrape.com/media/cache/2c/da/2cdad67c44b002e7ead0cc35693c0e8b.jpg",
                "source_url": "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html",
                "crawl_status": "success"
            }
        }

    @field_validator('availability')
    @classmethod
    def parse_availability(cls, v: str) -> str:
        """Ensure availability is a string."""
        return v.strip() if v else "Unknown"

    @field_validator('rating')
    @classmethod
    def validate_rating(cls, v: str) -> str:
        """Validate and normalize rating."""
        rating_map = {
            "One": "One",
            "Two": "Two",
            "Three": "Three",
            "Four": "Four",
            "Five": "Five",
        }
        return rating_map.get(v, v)


class ChangeType(str, Enum):
    """Type of change detected."""
    NEW_BOOK = "new_book"
    PRICE_CHANGE = "price_change"
    AVAILABILITY_CHANGE = "availability_change"
    CONTENT_CHANGE = "content_change"
    DELETED = "deleted"


class ChangeLog(BaseModel):
    """
    ChangeLog model for tracking changes to books.

    Stores what changed, when, and the old/new values.
    """
    book_id: str = Field(..., description="MongoDB _id of the book that changed")
    book_name: str = Field(..., description="Name of the book")
    change_type: ChangeType = Field(..., description="Type of change")
    change_timestamp: datetime = Field(default_factory=datetime.utcnow, description="When the change was detected")

    # Old and new values for comparison
    old_value: Optional[dict] = Field(None, description="Old value(s) before change")
    new_value: Optional[dict] = Field(None, description="New value(s) after change")

    # Additional context
    description: Optional[str] = Field(None, description="Human-readable description of the change")

    # MongoDB _id will be auto-generated
    id: Optional[str] = Field(None, alias="_id", description="MongoDB document ID")

    class Config:
        """Pydantic configuration."""
        populate_by_name = True
        json_schema_extra = {
            "example": {
                "book_id": "507f1f77bcf86cd799439011",
                "book_name": "A Light in the Attic",
                "change_type": "price_change",
                "old_value": {"price_incl_tax": 51.77},
                "new_value": {"price_incl_tax": 45.99},
                "description": "Price decreased from £51.77 to £45.99"
            }
        }


class CrawlCheckpoint(BaseModel):
    """
    Checkpoint model for resuming failed crawls.

    Stores the last successfully crawled page to allow resuming.
    """
    checkpoint_id: str = Field(default="main_crawl", description="Identifier for this checkpoint")
    last_page_url: str = Field(..., description="Last successfully crawled page URL")
    last_book_url: Optional[str] = Field(None, description="Last successfully crawled book URL")
    total_books_crawled: int = Field(0, description="Total books crawled so far", ge=0)
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="When checkpoint was created")
    status: CrawlStatus = Field(default=CrawlStatus.PARTIAL, description="Status of the crawl")

    # MongoDB _id will be auto-generated
    id: Optional[str] = Field(None, alias="_id", description="MongoDB document ID")

    class Config:
        """Pydantic configuration."""
        populate_by_name = True


class DailyReport(BaseModel):
    """Model for daily change reports."""
    report_date: datetime = Field(default_factory=datetime.utcnow, description="Date of the report")
    total_books: int = Field(0, description="Total books in database", ge=0)
    new_books: int = Field(0, description="New books added", ge=0)
    price_changes: int = Field(0, description="Number of price changes", ge=0)
    availability_changes: int = Field(0, description="Number of availability changes", ge=0)
    other_changes: int = Field(0, description="Other changes detected", ge=0)
    changes_details: list[dict] = Field(default_factory=list, description="Detailed list of changes")

    class Config:
        """Pydantic configuration."""
        json_schema_extra = {
            "example": {
                "report_date": "2025-11-05T10:00:00Z",
                "total_books": 1000,
                "new_books": 5,
                "price_changes": 12,
                "availability_changes": 3,
                "other_changes": 0
            }
        }