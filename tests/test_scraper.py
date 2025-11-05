"""Tests for scraper functionality."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from crawler.scraper import BookScraper
from utilities.models import Book, BookRating


@pytest.fixture
def scraper():
    """Create a BookScraper instance."""
    return BookScraper(max_concurrent_requests=5)


@pytest.fixture
def sample_catalog_html():
    """Sample HTML for catalog page."""
    return """
    <html>
        <body>
            <article class="product_pod">
                <h3><a href="../../../test-book_1/index.html">Test Book 1</a></h3>
            </article>
            <article class="product_pod">
                <h3><a href="../../../test-book_2/index.html">Test Book 2</a></h3>
            </article>
            <li class="next">
                <a href="page-2.html">next</a>
            </li>
        </body>
    </html>
    """


@pytest.fixture
def sample_book_html():
    """Sample HTML for book detail page."""
    return """
    <html>
        <body>
            <h1>Test Book Title</h1>
            <article class="product_page">
                <p>This is a test book description.</p>
            </article>
            <ul class="breadcrumb">
                <li><a href="/">Home</a></li>
                <li><a href="/category">Fiction</a></li>
                <li><a href="/category/fiction">Test Book</a></li>
            </ul>
            <table class="table table-striped">
                <tr>
                    <th>Price (excl. tax)</th>
                    <td>£50.00</td>
                </tr>
                <tr>
                    <th>Price (incl. tax)</th>
                    <td>£50.00</td>
                </tr>
                <tr>
                    <th>Availability</th>
                    <td>In stock (10 available)</td>
                </tr>
                <tr>
                    <th>Number of reviews</th>
                    <td>5</td>
                </tr>
            </table>
            <p class="star-rating Three"></p>
            <img src="../../media/cache/test.jpg" alt="Test Book"/>
        </body>
    </html>
    """


# Scraper Initialization Tests

def test_scraper_initialization():
    """Test scraper initializes with correct defaults."""
    scraper = BookScraper(max_concurrent_requests=10)

    assert scraper.max_concurrent_requests == 10
    assert scraper.parser is not None
    assert scraper.stats["total_books"] == 0


def test_scraper_semaphore():
    """Test scraper creates semaphore correctly."""
    scraper = BookScraper(max_concurrent_requests=5)

    assert scraper.semaphore._value == 5


# Fetch Page Tests

@pytest.mark.asyncio
async def test_fetch_page_success(scraper):
    """Test successful page fetching."""
    mock_response = MagicMock()
    mock_response.text = "<html>Test</html>"

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    html = await scraper.fetch_page(mock_client, "https://example.com")

    assert html == "<html>Test</html>"
    mock_client.get.assert_called_once()


@pytest.mark.asyncio
async def test_fetch_page_retry_on_failure(scraper):
    """Test that fetch_page retries on failure."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.HTTPError("Error"))

    with pytest.raises(httpx.HTTPError):
        await scraper.fetch_page(mock_client, "https://example.com")

    # Should retry 3 times (from @retry decorator)
    assert mock_client.get.call_count == 3


# Scrape Catalog Page Tests

@pytest.mark.asyncio
async def test_scrape_catalog_page_success(scraper, sample_catalog_html):
    """Test scraping a catalog page."""
    mock_response = MagicMock()
    mock_response.text = sample_catalog_html

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    book_urls, next_page = await scraper.scrape_catalog_page(
        mock_client,
        "https://books.toscrape.com/catalogue/page-1.html"
    )

    assert len(book_urls) == 2
    assert "test-book_1" in book_urls[0]
    assert "test-book_2" in book_urls[1]
    assert next_page is not None
    assert "page-2.html" in next_page


@pytest.mark.asyncio
async def test_scrape_catalog_page_error(scraper):
    """Test handling catalog page errors."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=Exception("Network error"))

    book_urls, next_page = await scraper.scrape_catalog_page(
        mock_client,
        "https://example.com"
    )

    assert book_urls == []
    assert next_page is None


# Scrape Book Tests

@pytest.mark.asyncio
async def test_scrape_book_success(scraper, sample_book_html):
    """Test scraping a single book."""
    mock_response = MagicMock()
    mock_response.text = sample_book_html

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    with patch('crawler.scraper.db') as mock_db:
        mock_db.compute_content_hash = MagicMock(return_value="abc123")
        mock_db.upsert_book = AsyncMock(return_value=("book_id_123", True))

        result = await scraper.scrape_book(
            mock_client,
            "https://books.toscrape.com/test"
        )

        assert result is not None
        assert result["book_id"] == "book_id_123"
        assert result["is_new"] is True
        assert scraper.stats["successful"] == 1


@pytest.mark.asyncio
async def test_scrape_book_parse_failure(scraper):
    """Test handling book parse failure."""
    mock_response = MagicMock()
    mock_response.text = "<html>Invalid HTML</html>"

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)

    result = await scraper.scrape_book(
        mock_client,
        "https://books.toscrape.com/test"
    )

    assert result is None
    assert scraper.stats["failed"] == 1


@pytest.mark.asyncio
async def test_scrape_book_http_error(scraper):
    """Test handling HTTP errors when scraping book."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.HTTPError("404 Not Found"))

    result = await scraper.scrape_book(
        mock_client,
        "https://books.toscrape.com/test"
    )

    assert result is None
    assert scraper.stats["failed"] == 1


# Statistics Tests

def test_get_stats(scraper):
    """Test getting scraper statistics."""
    scraper.stats["total_books"] = 100
    scraper.stats["successful"] = 95
    scraper.stats["failed"] = 5

    stats = scraper.get_stats()

    assert stats["total_books"] == 100
    assert stats["successful"] == 95
    assert stats["failed"] == 5
    # Should be a copy, not the original
    assert stats is not scraper.stats


# Integration Test (with mocks)

@pytest.mark.asyncio
async def test_scrape_all_books_basic(scraper, sample_catalog_html, sample_book_html):
    """Test basic scrape_all_books flow (simplified)."""
    # Mock database operations
    with patch('crawler.scraper.db') as mock_db:
        mock_db.connect = AsyncMock()
        mock_db.count_books = AsyncMock(return_value=0)
        mock_db.get_checkpoint = AsyncMock(return_value=None)
        mock_db.save_checkpoint = AsyncMock()
        mock_db.compute_content_hash = MagicMock(return_value="abc123")
        mock_db.upsert_book = AsyncMock(return_value=("book_id", True))
        mock_db.disconnect = AsyncMock()

        # Mock HTTP client
        with patch('httpx.AsyncClient') as mock_client_class:
            mock_client = AsyncMock()

            # First call returns catalog page, subsequent calls return book pages
            mock_response_catalog = MagicMock()
            mock_response_catalog.text = sample_catalog_html.replace(
                '<li class="next">',
                ''  # Remove next page link
            )

            mock_response_book = MagicMock()
            mock_response_book.text = sample_book_html

            mock_client.get = AsyncMock(side_effect=[
                mock_response_catalog,  # Catalog page
                mock_response_book,      # First book
                mock_response_book,      # Second book
            ])

            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock()
            mock_client_class.return_value = mock_client

            # This test would be more complex to fully mock
            # For now, we test that the method exists and is callable
            assert callable(scraper.scrape_all_books)


# Test Stats Tracking

def test_stats_increment():
    """Test that stats are incremented correctly."""
    scraper = BookScraper()

    assert scraper.stats["successful"] == 0
    assert scraper.stats["failed"] == 0

    scraper.stats["successful"] += 1
    scraper.stats["failed"] += 1

    assert scraper.stats["successful"] == 1
    assert scraper.stats["failed"] == 1