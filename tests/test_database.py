"""Tests for database operations."""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utilities.database import Database
from utilities.models import Book, ChangeLog, CrawlCheckpoint, ChangeType, BookRating, CrawlStatus


@pytest.fixture
def sample_book():
    """Create a sample book for testing."""
    return Book(
        name="Test Book",
        description="A test description",
        category="Fiction",
        price_excl_tax=50.0,
        price_incl_tax=50.0,
        availability="In stock (10 available)",
        num_available=10,
        num_reviews=5,
        rating=BookRating.THREE,
        image_url="https://example.com/image.jpg",
        source_url="https://books.toscrape.com/test-book",
    )


@pytest.fixture
def sample_change():
    """Create a sample change log entry."""
    return ChangeLog(
        book_id="507f1f77bcf86cd799439011",
        book_name="Test Book",
        change_type=ChangeType.PRICE_CHANGE,
        old_value={"price_incl_tax": 50.0},
        new_value={"price_incl_tax": 45.0},
        description="Price changed from £50.00 to £45.00"
    )


@pytest.fixture
def sample_checkpoint():
    """Create a sample checkpoint."""
    return CrawlCheckpoint(
        checkpoint_id="test_crawl",
        last_page_url="https://books.toscrape.com/catalogue/page-5.html",
        last_book_url="https://books.toscrape.com/catalogue/test_100/index.html",
        total_books_crawled=100,
        status=CrawlStatus.PARTIAL
    )


# Database Connection Tests

@pytest.mark.asyncio
async def test_database_connect():
    """Test database connection."""
    db = Database()

    with patch('utilities.database.AsyncIOMotorClient') as mock_client:
        mock_db = MagicMock()
        mock_db.books.create_indexes = AsyncMock()
        mock_db.changelog.create_indexes = AsyncMock()
        mock_db.checkpoints.create_indexes = AsyncMock()

        mock_client.return_value.admin.command = AsyncMock(return_value={"ok": 1})
        mock_client.return_value.__getitem__.return_value = mock_db

        await db.connect()

        assert db.client is not None
        assert db.db is not None


@pytest.mark.asyncio
async def test_database_connect_failure():
    """Test database connection failure."""
    db = Database()

    with patch('utilities.database.AsyncIOMotorClient') as mock_client:
        mock_client.return_value.admin.command = AsyncMock(side_effect=Exception("Connection failed"))

        with pytest.raises(Exception):
            await db.connect()


# Content Hash Tests

def test_compute_content_hash(sample_book):
    """Test content hash computation."""
    hash1 = Database.compute_content_hash(sample_book)

    assert hash1 is not None
    assert len(hash1) == 64  # SHA256 hex digest length
    assert isinstance(hash1, str)


def test_compute_content_hash_consistency(sample_book):
    """Test that same book produces same hash."""
    hash1 = Database.compute_content_hash(sample_book)
    hash2 = Database.compute_content_hash(sample_book)

    assert hash1 == hash2


def test_compute_content_hash_different_books():
    """Test that different books produce different hashes."""
    book1 = Book(
        name="Book 1",
        category="Fiction",
        price_excl_tax=50.0,
        price_incl_tax=50.0,
        availability="In stock",
        num_available=10,
        num_reviews=5,
        rating=BookRating.THREE,
        image_url="https://example.com/1.jpg",
        source_url="https://books.toscrape.com/book1",
    )

    book2 = Book(
        name="Book 2",
        category="Fiction",
        price_excl_tax=60.0,  # Different price
        price_incl_tax=60.0,
        availability="In stock",
        num_available=10,
        num_reviews=5,
        rating=BookRating.THREE,
        image_url="https://example.com/2.jpg",
        source_url="https://books.toscrape.com/book2",
    )

    hash1 = Database.compute_content_hash(book1)
    hash2 = Database.compute_content_hash(book2)

    assert hash1 != hash2


# Book Operations Tests

@pytest.mark.asyncio
async def test_insert_book(sample_book):
    """Test inserting a book."""
    db = Database()
    mock_db = MagicMock()
    mock_collection = MagicMock()

    mock_result = MagicMock()
    mock_result.inserted_id = "507f1f77bcf86cd799439011"
    mock_collection.insert_one = AsyncMock(return_value=mock_result)

    mock_db.books = mock_collection
    db.db = mock_db

    book_id = await db.insert_book(sample_book)

    assert book_id == "507f1f77bcf86cd799439011"
    mock_collection.insert_one.assert_called_once()


@pytest.mark.asyncio
async def test_upsert_book_new(sample_book):
    """Test upserting a new book."""
    db = Database()
    mock_db = MagicMock()
    mock_collection = MagicMock()

    mock_result = MagicMock()
    mock_result.upserted_id = "507f1f77bcf86cd799439011"
    mock_collection.update_one = AsyncMock(return_value=mock_result)

    mock_db.books = mock_collection
    db.db = mock_db

    book_id, is_new = await db.upsert_book(sample_book)

    assert is_new is True
    assert book_id == "507f1f77bcf86cd799439011"


@pytest.mark.asyncio
async def test_upsert_book_existing(sample_book):
    """Test upserting an existing book."""
    db = Database()
    mock_db = MagicMock()
    mock_collection = MagicMock()

    mock_result = MagicMock()
    mock_result.upserted_id = None  # Not a new insert
    mock_collection.update_one = AsyncMock(return_value=mock_result)
    mock_collection.find_one = AsyncMock(return_value={"_id": "507f1f77bcf86cd799439011"})

    mock_db.books = mock_collection
    db.db = mock_db

    book_id, is_new = await db.upsert_book(sample_book)

    assert is_new is False
    assert book_id == "507f1f77bcf86cd799439011"


@pytest.mark.asyncio
async def test_get_book_by_url(sample_book):
    """Test retrieving a book by URL."""
    db = Database()
    mock_db = MagicMock()
    mock_collection = MagicMock()

    book_dict = sample_book.model_dump()
    book_dict["_id"] = "507f1f77bcf86cd799439011"
    mock_collection.find_one = AsyncMock(return_value=book_dict)

    mock_db.books = mock_collection
    db.db = mock_db

    result = await db.get_book_by_url(sample_book.source_url)

    assert result is not None
    assert result.name == sample_book.name
    assert result.id == "507f1f77bcf86cd799439011"


@pytest.mark.asyncio
async def test_get_book_by_url_not_found():
    """Test retrieving non-existent book returns None."""
    db = Database()
    mock_db = MagicMock()
    mock_collection = MagicMock()

    mock_collection.find_one = AsyncMock(return_value=None)

    mock_db.books = mock_collection
    db.db = mock_db

    result = await db.get_book_by_url("https://example.com/nonexistent")

    assert result is None


@pytest.mark.asyncio
async def test_count_books():
    """Test counting books."""
    db = Database()
    mock_db = MagicMock()
    mock_collection = MagicMock()

    mock_collection.count_documents = AsyncMock(return_value=1000)

    mock_db.books = mock_collection
    db.db = mock_db

    count = await db.count_books()

    assert count == 1000


# ChangeLog Operations Tests

@pytest.mark.asyncio
async def test_insert_change(sample_change):
    """Test inserting a change log entry."""
    db = Database()
    mock_db = MagicMock()
    mock_collection = MagicMock()

    mock_result = MagicMock()
    mock_result.inserted_id = "507f1f77bcf86cd799439012"
    mock_collection.insert_one = AsyncMock(return_value=mock_result)

    mock_db.changelog = mock_collection
    db.db = mock_db

    change_id = await db.insert_change(sample_change)

    assert change_id == "507f1f77bcf86cd799439012"


@pytest.mark.asyncio
async def test_get_recent_changes():
    """Test retrieving recent changes."""
    db = Database()
    mock_db = MagicMock()
    mock_collection = MagicMock()

    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.limit.return_value = mock_cursor
    mock_cursor.__aiter__.return_value = [
        {"_id": "1", "change_type": "new_book", "book_name": "Book 1"},
        {"_id": "2", "change_type": "price_change", "book_name": "Book 2"},
    ].__iter__()

    mock_collection.find.return_value = mock_cursor
    mock_db.changelog = mock_collection
    db.db = mock_db

    changes = await db.get_recent_changes(limit=2)

    assert len(changes) == 2
    assert changes[0]["change_type"] == "new_book"


# Checkpoint Operations Tests

@pytest.mark.asyncio
async def test_save_checkpoint(sample_checkpoint):
    """Test saving a checkpoint."""
    db = Database()
    mock_db = MagicMock()
    mock_collection = MagicMock()

    mock_collection.update_one = AsyncMock()

    mock_db.checkpoints = mock_collection
    db.db = mock_db

    await db.save_checkpoint(sample_checkpoint)

    mock_collection.update_one.assert_called_once()


@pytest.mark.asyncio
async def test_get_checkpoint(sample_checkpoint):
    """Test retrieving a checkpoint."""
    db = Database()
    mock_db = MagicMock()
    mock_collection = MagicMock()

    checkpoint_dict = sample_checkpoint.model_dump()
    checkpoint_dict["_id"] = "507f1f77bcf86cd799439013"
    mock_collection.find_one = AsyncMock(return_value=checkpoint_dict)

    mock_db.checkpoints = mock_collection
    db.db = mock_db

    result = await db.get_checkpoint("test_crawl")

    assert result is not None
    assert result.checkpoint_id == "test_crawl"
    assert result.total_books_crawled == 100


@pytest.mark.asyncio
async def test_get_checkpoint_not_found():
    """Test retrieving non-existent checkpoint returns None."""
    db = Database()
    mock_db = MagicMock()
    mock_collection = MagicMock()

    mock_collection.find_one = AsyncMock(return_value=None)

    mock_db.checkpoints = mock_collection
    db.db = mock_db

    result = await db.get_checkpoint("nonexistent")

    assert result is None


# Query Tests

@pytest.mark.asyncio
async def test_get_all_books_with_filters():
    """Test getting books with filters."""
    db = Database()
    mock_db = MagicMock()
    mock_collection = MagicMock()

    mock_cursor = MagicMock()
    mock_cursor.find.return_value = mock_cursor
    mock_cursor.skip.return_value = mock_cursor
    mock_cursor.limit.return_value = mock_cursor
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.__aiter__.return_value = [
        {"_id": "1", "name": "Book 1", "category": "Fiction", "price_incl_tax": 25.0},
    ].__iter__()

    mock_collection.find.return_value = mock_cursor
    mock_db.books = mock_collection
    db.db = mock_db

    books = await db.get_all_books(
        category="Fiction",
        min_price=20.0,
        max_price=30.0,
        skip=0,
        limit=10
    )

    assert len(books) == 1
    assert books[0]["category"] == "Fiction"