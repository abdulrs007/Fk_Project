"""Tests for API endpoints."""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

# Import the FastAPI app
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.main import app
from utilities.models import Book, BookRating, CrawlStatus


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def mock_db():
    """Mock database for testing."""
    with patch('api.routes.db') as mock:
        yield mock


@pytest.fixture
def sample_book_data():
    """Sample book data for testing."""
    return {
        "_id": "507f1f77bcf86cd799439011",
        "name": "Test Book",
        "description": "A test book description",
        "category": "Fiction",
        "price_excl_tax": 50.0,
        "price_incl_tax": 50.0,
        "availability": "In stock (10 available)",
        "num_available": 10,
        "num_reviews": 5,
        "rating": "Three",
        "image_url": "https://example.com/image.jpg",
        "source_url": "https://books.toscrape.com/test",
        "crawl_timestamp": datetime.utcnow(),
    }


@pytest.fixture
def sample_change_data():
    """Sample change log data for testing."""
    return {
        "_id": "507f1f77bcf86cd799439012",
        "book_id": "507f1f77bcf86cd799439011",
        "book_name": "Test Book",
        "change_type": "price_change",
        "change_timestamp": datetime.utcnow(),
        "old_value": {"price_incl_tax": 50.0},
        "new_value": {"price_incl_tax": 45.0},
        "description": "Price changed from £50.00 to £45.00"
    }


# Health Check Tests

def test_health_check_success(client, mock_db):
    """Test health check endpoint returns healthy status."""
    mock_db.count_books = AsyncMock(return_value=1000)

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data
    assert data["database"] == "connected"
    assert data["total_books"] == 1000


def test_health_check_db_error(client, mock_db):
    """Test health check when database fails."""
    mock_db.count_books = AsyncMock(side_effect=Exception("DB Error"))

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "unhealthy"
    assert data["database"] == "disconnected"
    assert data["total_books"] == 0


# Books Endpoint Tests

def test_list_books_without_auth(client):
    """Test that books endpoint requires authentication."""
    response = client.get("/api/v1/books")

    assert response.status_code == 403
    assert "API key" in response.json()["detail"]


def test_list_books_with_invalid_auth(client):
    """Test books endpoint with invalid API key."""
    response = client.get(
        "/api/v1/books",
        headers={"X-API-Key": "invalid-key"}
    )

    assert response.status_code == 403


def test_list_books_success(client, mock_db, sample_book_data):
    """Test successful books listing."""
    mock_db.get_all_books = AsyncMock(return_value=[sample_book_data])
    mock_db.count_books = AsyncMock(return_value=1)

    response = client.get(
        "/api/v1/books",
        headers={"X-API-Key": "dev-api-key-12345"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["page"] == 1
    assert data["page_size"] == 50
    assert len(data["books"]) == 1
    assert data["books"][0]["name"] == "Test Book"


def test_list_books_with_pagination(client, mock_db, sample_book_data):
    """Test books listing with pagination."""
    mock_db.get_all_books = AsyncMock(return_value=[sample_book_data] * 5)
    mock_db.count_books = AsyncMock(return_value=100)

    response = client.get(
        "/api/v1/books?page=2&page_size=5",
        headers={"X-API-Key": "dev-api-key-12345"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["page"] == 2
    assert data["page_size"] == 5
    assert data["total"] == 100
    assert data["total_pages"] == 20


def test_list_books_with_category_filter(client, mock_db, sample_book_data):
    """Test books filtering by category."""
    mock_db.get_all_books = AsyncMock(return_value=[sample_book_data])
    mock_db.count_books = AsyncMock(return_value=1)

    response = client.get(
        "/api/v1/books?category=Fiction",
        headers={"X-API-Key": "dev-api-key-12345"}
    )

    assert response.status_code == 200
    # Verify the mock was called with category filter
    call_kwargs = mock_db.get_all_books.call_args[1]
    assert call_kwargs["category"] == "Fiction"


def test_list_books_with_price_filter(client, mock_db, sample_book_data):
    """Test books filtering by price range."""
    mock_db.get_all_books = AsyncMock(return_value=[sample_book_data])
    mock_db.count_books = AsyncMock(return_value=1)

    response = client.get(
        "/api/v1/books?min_price=20&max_price=60",
        headers={"X-API-Key": "dev-api-key-12345"}
    )

    assert response.status_code == 200
    call_kwargs = mock_db.get_all_books.call_args[1]
    assert call_kwargs["min_price"] == 20
    assert call_kwargs["max_price"] == 60


def test_list_books_with_rating_filter(client, mock_db, sample_book_data):
    """Test books filtering by rating."""
    mock_db.get_all_books = AsyncMock(return_value=[sample_book_data])
    mock_db.count_books = AsyncMock(return_value=1)

    response = client.get(
        "/api/v1/books?rating=Five",
        headers={"X-API-Key": "dev-api-key-12345"}
    )

    assert response.status_code == 200
    call_kwargs = mock_db.get_all_books.call_args[1]
    assert call_kwargs["rating"] == "Five"


def test_list_books_with_sorting(client, mock_db, sample_book_data):
    """Test books sorting."""
    mock_db.get_all_books = AsyncMock(return_value=[sample_book_data])
    mock_db.count_books = AsyncMock(return_value=1)

    response = client.get(
        "/api/v1/books?sort_by=price_incl_tax&sort_order=asc",
        headers={"X-API-Key": "dev-api-key-12345"}
    )

    assert response.status_code == 200
    call_kwargs = mock_db.get_all_books.call_args[1]
    assert call_kwargs["sort_by"] == "price_incl_tax"


def test_list_books_invalid_sort_order(client, mock_db):
    """Test invalid sort order returns error."""
    response = client.get(
        "/api/v1/books?sort_order=invalid",
        headers={"X-API-Key": "dev-api-key-12345"}
    )

    assert response.status_code == 400
    assert "sort_order" in response.json()["detail"]


# Get Book by ID Tests

def test_get_book_by_id_success(client, mock_db, sample_book_data):
    """Test getting a specific book by ID."""
    mock_db.books.find_one = AsyncMock(return_value=sample_book_data)

    response = client.get(
        "/api/v1/books/507f1f77bcf86cd799439011",
        headers={"X-API-Key": "dev-api-key-12345"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "507f1f77bcf86cd799439011"
    assert data["name"] == "Test Book"


def test_get_book_by_id_not_found(client, mock_db):
    """Test getting non-existent book returns 404."""
    mock_db.books.find_one = AsyncMock(return_value=None)

    response = client.get(
        "/api/v1/books/507f1f77bcf86cd799439011",
        headers={"X-API-Key": "dev-api-key-12345"}
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_get_book_by_id_invalid_id(client):
    """Test invalid book ID format returns 400."""
    response = client.get(
        "/api/v1/books/invalid-id",
        headers={"X-API-Key": "dev-api-key-12345"}
    )

    assert response.status_code == 400
    assert "Invalid book ID" in response.json()["detail"]


# Changes Endpoint Tests

def test_list_changes_success(client, mock_db, sample_change_data):
    """Test listing changes."""
    # Mock the cursor operations
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.skip.return_value = mock_cursor
    mock_cursor.limit.return_value = mock_cursor
    mock_cursor.__aiter__.return_value = [sample_change_data].__iter__()

    mock_db.changelog.count_documents = AsyncMock(return_value=1)
    mock_db.changelog.find.return_value = mock_cursor

    response = client.get(
        "/api/v1/changes",
        headers={"X-API-Key": "dev-api-key-12345"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert len(data["changes"]) == 1


def test_list_changes_with_filter(client, mock_db, sample_change_data):
    """Test filtering changes by type."""
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.skip.return_value = mock_cursor
    mock_cursor.limit.return_value = mock_cursor
    mock_cursor.__aiter__.return_value = [sample_change_data].__iter__()

    mock_db.changelog.count_documents = AsyncMock(return_value=1)
    mock_db.changelog.find.return_value = mock_cursor

    response = client.get(
        "/api/v1/changes?change_type=price_change",
        headers={"X-API-Key": "dev-api-key-12345"}
    )

    assert response.status_code == 200


def test_list_changes_invalid_type(client, mock_db):
    """Test invalid change type returns error."""
    response = client.get(
        "/api/v1/changes?change_type=invalid_type",
        headers={"X-API-Key": "dev-api-key-12345"}
    )

    assert response.status_code == 400


# Categories Endpoint Tests

def test_list_categories_success(client, mock_db):
    """Test listing all categories."""
    mock_db.books.distinct = AsyncMock(return_value=["Fiction", "Poetry", "History"])

    response = client.get(
        "/api/v1/categories",
        headers={"X-API-Key": "dev-api-key-12345"}
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    assert "Fiction" in data
    assert "Poetry" in data


# Rate Limiting Tests

def test_rate_limiting(client, mock_db, sample_book_data):
    """Test that rate limiting works (this is a basic check)."""
    mock_db.get_all_books = AsyncMock(return_value=[sample_book_data])
    mock_db.count_books = AsyncMock(return_value=1)

    # Make multiple requests
    responses = []
    for _ in range(5):
        response = client.get(
            "/api/v1/books",
            headers={"X-API-Key": "dev-api-key-12345"}
        )
        responses.append(response.status_code)

    # All should succeed (we're under limit in test)
    assert all(code == 200 for code in responses)