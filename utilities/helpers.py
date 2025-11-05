"""Helper utilities for the crawler project."""
import re
from typing import Optional
from urllib.parse import urljoin


def extract_number_from_availability(availability: str) -> int:
    """
    Extract the number of available items from availability string.

    Example: "In stock (22 available)" -> 22
    """
    match = re.search(r'\((\d+)\s+available\)', availability)
    if match:
        return int(match.group(1))
    return 0


def extract_price(price_text: str) -> float:
    """
    Extract price from text like "£51.77".

    Removes currency symbols and converts to float.
    """
    # Remove currency symbols and whitespace
    price_str = re.sub(r'[£$€,\s]', '', price_text)
    try:
        return float(price_str)
    except ValueError:
        return 0.0


def normalize_rating(rating_class: str) -> Optional[str]:
    """
    Normalize rating from CSS class name.

    Example: "star-rating Three" -> "Three"
    """
    rating_map = {
        'One': 'One',
        'Two': 'Two',
        'Three': 'Three',
        'Four': 'Four',
        'Five': 'Five',
    }

    for key in rating_map:
        if key in rating_class:
            return rating_map[key]

    return None


def make_absolute_url(base_url: str, relative_url: str) -> str:
    """
    Convert relative URL to absolute URL.

    Example:
        base: https://books.toscrape.com/
        relative: catalogue/book_1/index.html
        result: https://books.toscrape.com/catalogue/book_1/index.html
    """
    return urljoin(base_url, relative_url)


def clean_text(text: Optional[str]) -> str:
    """
    Clean text by removing extra whitespace and newlines.
    """
    if not text:
        return ""

    # Replace multiple whitespace with single space
    text = re.sub(r'\s+', ' ', text)
    return text.strip()