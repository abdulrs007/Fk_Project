"""Tests for change detection logic."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scheduler.detector import ChangeDetector
from utilities.models import Book, BookRating, ChangeType, ChangeLog


@pytest.fixture
def detector():
    """Create a ChangeDetector instance."""
    return ChangeDetector()


@pytest.fixture
def old_book():
    """Create an old version of a book."""
    return Book(
        name="Test Book",
        description="Old description",
        category="Fiction",
        price_excl_tax=50.0,
        price_incl_tax=50.0,
        availability="In stock (10 available)",
        num_available=10,
        num_reviews=5,
        rating=BookRating.THREE,
        image_url="https://example.com/old.jpg",
        source_url="https://books.toscrape.com/test",
        content_hash="old_hash_123",
        id="507f1f77bcf86cd799439011"
    )


@pytest.fixture
def new_book_price_changed():
    """Create a new version with price change."""
    return Book(
        name="Test Book",
        description="Old description",
        category="Fiction",
        price_excl_tax=45.0,  # Changed
        price_incl_tax=45.0,  # Changed
        availability="In stock (10 available)",
        num_available=10,
        num_reviews=5,
        rating=BookRating.THREE,
        image_url="https://example.com/old.jpg",
        source_url="https://books.toscrape.com/test",
        content_hash="new_hash_456"
    )


@pytest.fixture
def new_book_availability_changed():
    """Create a new version with availability change."""
    return Book(
        name="Test Book",
        description="Old description",
        category="Fiction",
        price_excl_tax=50.0,
        price_incl_tax=50.0,
        availability="In stock (5 available)",  # Changed
        num_available=5,  # Changed
        num_reviews=5,
        rating=BookRating.THREE,
        image_url="https://example.com/old.jpg",
        source_url="https://books.toscrape.com/test",
        content_hash="new_hash_789"
    )


# Initialization Tests

def test_detector_initialization():
    """Test detector initializes correctly."""
    detector = ChangeDetector()

    assert detector.changes == []
    assert detector.stats["new_books"] == 0
    assert detector.stats["price_changes"] == 0
    assert detector.stats["availability_changes"] == 0


# Compare Books Tests

@pytest.mark.asyncio
async def test_compare_books_price_change(detector, old_book, new_book_price_changed):
    """Test detecting price changes."""
    changes = await detector.compare_books(old_book, new_book_price_changed)

    assert len(changes) == 1
    assert changes[0].change_type == ChangeType.PRICE_CHANGE
    assert changes[0].old_value["price_incl_tax"] == 50.0
    assert changes[0].new_value["price_incl_tax"] == 45.0
    assert "£50.00 to £45.00" in changes[0].description


@pytest.mark.asyncio
async def test_compare_books_availability_change(detector, old_book, new_book_availability_changed):
    """Test detecting availability changes."""
    changes = await detector.compare_books(old_book, new_book_availability_changed)

    assert len(changes) == 1
    assert changes[0].change_type == ChangeType.AVAILABILITY_CHANGE
    assert changes[0].old_value["num_available"] == 10
    assert changes[0].new_value["num_available"] == 5


@pytest.mark.asyncio
async def test_compare_books_no_change(detector, old_book):
    """Test no changes detected when books are identical."""
    new_book = Book(**old_book.model_dump())
    new_book.content_hash = old_book.content_hash  # Same hash

    changes = await detector.compare_books(old_book, new_book)

    assert len(changes) == 0


@pytest.mark.asyncio
async def test_compare_books_reviews_change(detector, old_book):
    """Test detecting review count changes."""
    new_book = Book(**old_book.model_dump())
    new_book.num_reviews = 10  # Changed from 5 to 10
    new_book.content_hash = "different_hash"

    changes = await detector.compare_books(old_book, new_book)

    assert len(changes) == 1
    assert changes[0].change_type == ChangeType.CONTENT_CHANGE
    assert "Reviews changed" in changes[0].description


@pytest.mark.asyncio
async def test_compare_books_multiple_changes(detector, old_book):
    """Test detecting multiple changes at once."""
    new_book = Book(**old_book.model_dump())
    new_book.price_incl_tax = 45.0  # Price changed
    new_book.num_available = 5      # Availability changed
    new_book.content_hash = "different_hash"

    changes = await detector.compare_books(old_book, new_book)

    assert len(changes) == 2
    change_types = [c.change_type for c in changes]
    assert ChangeType.PRICE_CHANGE in change_types
    assert ChangeType.AVAILABILITY_CHANGE in change_types


# Check Book Tests

@pytest.mark.asyncio
async def test_check_book_new_book(detector):
    """Test detecting a completely new book."""
    sample_html = """
    <html><body>
        <h1>New Book</h1>
        <article class="product_page"><p>Description</p></article>
        <ul class="breadcrumb">
            <li><a href="/">Home</a></li>
            <li><a href="/cat">Fiction</a></li>
        </ul>
        <table class="table-striped">
            <tr><th>Price (excl. tax)</th><td>£30.00</td></tr>
            <tr><th>Price (incl. tax)</th><td>£30.00</td></tr>
            <tr><th>Availability</th><td>In stock (5 available)</td></tr>
            <tr><th>Number of reviews</th><td>0</td></tr>
        </table>
        <p class="star-rating Four"></p>
        <img src="image.jpg"/>
    </body></html>
    """

    mock_response = MagicMock()
    mock_response.text = sample_html

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch('scheduler.detector.db') as mock_db:
        mock_db.get_book_by_url = AsyncMock(return_value=None)  # Book doesn't exist
        mock_db.compute_content_hash = MagicMock(return_value="hash123")
        mock_db.upsert_book = AsyncMock(return_value=("new_book_id", True))

        await detector._check_book(mock_client, "https://books.toscrape.com/new-book")

        assert detector.stats["new_books"] == 1
        assert len(detector.changes) == 1
        assert detector.changes[0].change_type == ChangeType.NEW_BOOK


@pytest.mark.asyncio
async def test_check_book_unchanged(detector, old_book):
    """Test detecting unchanged book."""
    sample_html = """
    <html><body>
        <h1>Test Book</h1>
        <article class="product_page"><p>Old description</p></article>
        <ul class="breadcrumb">
            <li><a href="/">Home</a></li>
            <li><a href="/cat">Fiction</a></li>
        </ul>
        <table class="table-striped">
            <tr><th>Price (excl. tax)</th><td>£50.00</td></tr>
            <tr><th>Price (incl. tax)</th><td>£50.00</td></tr>
            <tr><th>Availability</th><td>In stock (10 available)</td></tr>
            <tr><th>Number of reviews</th><td>5</td></tr>
        </table>
        <p class="star-rating Three"></p>
        <img src="old.jpg"/>
    </body></html>
    """

    mock_response = MagicMock()
    mock_response.text = sample_html

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch('scheduler.detector.db') as mock_db:
        mock_db.get_book_by_url = AsyncMock(return_value=old_book)
        mock_db.compute_content_hash = MagicMock(return_value="old_hash_123")  # Same hash
        mock_db.upsert_book = AsyncMock()

        await detector._check_book(mock_client, "https://books.toscrape.com/test")

        assert detector.stats["unchanged"] == 1
        assert len(detector.changes) == 0  # No changes logged


# Statistics Tests

def test_get_changes(detector):
    """Test getting changes list."""
    change1 = ChangeLog(
        book_id="1",
        book_name="Book 1",
        change_type=ChangeType.NEW_BOOK,
        description="New book"
    )

    detector.changes.append(change1)
    changes = detector.get_changes()

    assert len(changes) == 1
    assert changes[0].book_name == "Book 1"
    # Should be a copy
    assert changes is not detector.changes


# Log Changes Tests

@pytest.mark.asyncio
async def test_log_changes_with_data(detector):
    """Test logging changes to database."""
    change = ChangeLog(
        book_id="1",
        book_name="Book 1",
        change_type=ChangeType.PRICE_CHANGE,
        description="Price changed"
    )
    detector.changes.append(change)

    with patch('scheduler.detector.db') as mock_db:
        mock_db.insert_change = AsyncMock()

        await detector._log_changes()

        mock_db.insert_change.assert_called_once()


@pytest.mark.asyncio
async def test_log_changes_no_data(detector):
    """Test logging with no changes."""
    with patch('scheduler.detector.db') as mock_db:
        mock_db.insert_change = AsyncMock()

        await detector._log_changes()

        mock_db.insert_change.assert_not_called()


# Detect Changes Integration Test

@pytest.mark.asyncio
async def test_detect_changes_basic_flow(detector):
    """Test basic detect_changes flow."""
    with patch('scheduler.detector.db') as mock_db:
        mock_db.count_books = AsyncMock(side_effect=[100, 105])  # 5 new books
        mock_db.insert_change = AsyncMock()

        with patch.object(detector, '_crawl_and_compare', new=AsyncMock()):
            # Simulate finding 5 new books
            for i in range(5):
                change = ChangeLog(
                    book_id=f"book_{i}",
                    book_name=f"Book {i}",
                    change_type=ChangeType.NEW_BOOK,
                    description=f"New book {i}"
                )
                detector.changes.append(change)
                detector.stats["new_books"] += 1

            summary = await detector.detect_changes()

            assert summary["initial_book_count"] == 100
            assert summary["final_book_count"] == 105
            assert summary["new_books"] == 5
            assert summary["total_changes"] == 5


# Error Handling Tests

@pytest.mark.asyncio
async def test_check_book_http_error(detector):
    """Test handling HTTP errors."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=Exception("HTTP Error"))

    await detector._check_book(mock_client, "https://example.com/book")

    # Should handle error gracefully without crashing
    assert detector.stats["new_books"] == 0


@pytest.mark.asyncio
async def test_check_book_parse_failure(detector):
    """Test handling parse failures."""
    mock_response = MagicMock()
    mock_response.text = "<html>Invalid</html>"

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    await detector._check_book(mock_client, "https://example.com/book")

    # Should handle error gracefully
    assert detector.stats["new_books"] == 0