"""Tests for HTML parser."""
import pytest
from crawler.parser import BookParser


@pytest.fixture
def parser():
    """Create a BookParser instance."""
    return BookParser()


@pytest.fixture
def sample_book_html():
    """Sample HTML for a book detail page."""
    return """
    <html>
        <body>
            <h1>Test Book</h1>
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


@pytest.fixture
def sample_catalog_html():
    """Sample HTML for a catalog page."""
    return """
    <html>
        <body>
            <article class="product_pod">
                <h3><a href="catalogue/book1.html">Book 1</a></h3>
            </article>
            <article class="product_pod">
                <h3><a href="catalogue/book2.html">Book 2</a></h3>
            </article>
            <li class="next">
                <a href="page-2.html">next</a>
            </li>
        </body>
    </html>
    """


def test_parse_book_list_page(parser, sample_catalog_html):
    """Test parsing a catalog page to extract book URLs."""
    book_urls = parser.parse_book_list_page(sample_catalog_html)

    assert len(book_urls) == 2
    assert "catalogue/book1.html" in book_urls[0]
    assert "catalogue/book2.html" in book_urls[1]


def test_get_next_page_url(parser, sample_catalog_html):
    """Test extracting next page URL from pagination."""
    next_url = parser.get_next_page_url(sample_catalog_html, "https://books.toscrape.com/page-1.html")

    assert next_url is not None
    assert "page-2.html" in next_url


def test_parse_book_detail_page(parser, sample_book_html):
    """Test parsing a book detail page."""
    book = parser.parse_book_detail_page(sample_book_html, "https://books.toscrape.com/test")

    assert book is not None
    assert book.name == "Test Book"
    assert book.description == "This is a test book description."
    assert book.category == "Fiction"
    assert book.price_excl_tax == 50.0
    assert book.price_incl_tax == 50.0
    assert book.num_available == 10
    assert book.num_reviews == 5
    assert book.rating == "Three"


def test_parse_book_missing_name(parser):
    """Test parsing book without name returns None."""
    html = "<html><body></body></html>"
    book = parser.parse_book_detail_page(html, "https://test.com")

    assert book is None