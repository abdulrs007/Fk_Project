"""Tests for utility helper functions."""
import pytest
from utilities.helpers import (
    extract_number_from_availability,
    extract_price,
    normalize_rating,
    make_absolute_url,
    clean_text
)


def test_extract_number_from_availability():
    """Test extracting number from availability string."""
    assert extract_number_from_availability("In stock (22 available)") == 22
    assert extract_number_from_availability("In stock (1 available)") == 1
    assert extract_number_from_availability("Out of stock") == 0


def test_extract_price():
    """Test extracting price from formatted string."""
    assert extract_price("£51.77") == 51.77
    assert extract_price("$25.99") == 25.99
    assert extract_price("€10.50") == 10.50
    assert extract_price("invalid") == 0.0


def test_normalize_rating():
    """Test normalizing rating from CSS class."""
    assert normalize_rating("star-rating Three") == "Three"
    assert normalize_rating("star-rating Five") == "Five"
    assert normalize_rating("One") == "One"
    assert normalize_rating("invalid") is None


def test_make_absolute_url():
    """Test converting relative URL to absolute."""
    base = "https://books.toscrape.com/"
    relative = "catalogue/book_1/index.html"
    absolute = make_absolute_url(base, relative)

    assert absolute == "https://books.toscrape.com/catalogue/book_1/index.html"


def test_clean_text():
    """Test cleaning text with extra whitespace."""
    assert clean_text("  Hello   World  ") == "Hello World"
    assert clean_text("Test\n\nBook") == "Test Book"
    assert clean_text(None) == ""