"""HTML parsing logic for extracting book data."""
from typing import Optional, List
from bs4 import BeautifulSoup
from loguru import logger

from utilities.models import Book, BookRating, CrawlStatus
from utilities.helpers import (
    extract_number_from_availability,
    extract_price,
    normalize_rating,
    make_absolute_url,
    clean_text
)


class BookParser:
    """Parser for extracting book information from HTML."""

    def __init__(self, base_url: str = "https://books.toscrape.com"):
        """Initialize parser with base URL."""
        self.base_url = base_url

    def parse_book_list_page(self, html: str, current_page_url: str = None) -> List[str]:
        """
        Parse a catalog page and extract book detail page URLs.

        Args:
            html: HTML content of the catalog page
            current_page_url: URL of the current catalog page (for resolving relative URLs)

        Returns:
            List of absolute URLs to book detail pages
        """
        soup = BeautifulSoup(html, 'lxml')
        book_urls = []

        # Use current page URL or base URL for resolving relative URLs
        base_for_resolution = current_page_url or f"{self.base_url}/catalogue/"

        # Find all book containers
        articles = soup.find_all('article', class_='product_pod')

        for article in articles:
            # Find the link to the book's detail page
            h3_tag = article.find('h3')
            if h3_tag:
                a_tag = h3_tag.find('a')
                if a_tag and a_tag.get('href'):
                    relative_url = a_tag['href']
                    # Convert relative URL to absolute
                    absolute_url = make_absolute_url(base_for_resolution, relative_url)
                    book_urls.append(absolute_url)

        logger.debug(f"Found {len(book_urls)} books on page")
        return book_urls

    def get_next_page_url(self, html: str, current_url: str) -> Optional[str]:
        """
        Extract the URL of the next page from pagination.

        Args:
            html: HTML content of current page
            current_url: Current page URL for constructing absolute URL

        Returns:
            Absolute URL of next page, or None if no next page
        """
        soup = BeautifulSoup(html, 'lxml')

        # Find pagination
        next_link = soup.find('li', class_='next')
        if next_link:
            a_tag = next_link.find('a')
            if a_tag and a_tag.get('href'):
                relative_url = a_tag['href']
                # Make URL absolute relative to current page
                absolute_url = make_absolute_url(current_url, relative_url)
                return absolute_url

        return None

    def parse_book_detail_page(self, html: str, source_url: str) -> Optional[Book]:
        """
        Parse a book detail page and extract all book information.

        Args:
            html: HTML content of the book detail page
            source_url: Original URL of the page

        Returns:
            Book object with extracted data, or None if parsing fails
        """
        try:
            soup = BeautifulSoup(html, 'lxml')

            # Extract book name
            name = self._extract_name(soup)
            if not name:
                logger.warning(f"Could not extract book name from {source_url}")
                return None

            # Extract description
            description = self._extract_description(soup)

            # Extract category
            category = self._extract_category(soup)

            # Extract prices
            price_excl_tax, price_incl_tax = self._extract_prices(soup)

            # Extract availability
            availability, num_available = self._extract_availability(soup)

            # Extract number of reviews
            num_reviews = self._extract_num_reviews(soup)

            # Extract rating
            rating = self._extract_rating(soup)

            # Extract image URL
            image_url = self._extract_image_url(soup)

            # Create Book object
            book = Book(
                name=name,
                description=description,
                category=category,
                price_excl_tax=price_excl_tax,
                price_incl_tax=price_incl_tax,
                availability=availability,
                num_available=num_available,
                num_reviews=num_reviews,
                rating=rating,
                image_url=image_url,
                source_url=source_url,
                raw_html=html,  # Store raw HTML for fallback
                crawl_status=CrawlStatus.SUCCESS
            )

            logger.debug(f"Successfully parsed book: {name}")
            return book

        except Exception as e:
            logger.error(f"Error parsing book page {source_url}: {e}")
            return None

    def _extract_name(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract book name/title."""
        h1_tag = soup.find('h1')
        return clean_text(h1_tag.text) if h1_tag else None

    def _extract_description(self, soup: BeautifulSoup) -> Optional[str]:
        """Extract book description."""
        # Description is in the <article> tag, in a <p> without class
        article = soup.find('article', class_='product_page')
        if article:
            # Find all <p> tags
            p_tags = article.find_all('p', class_=False)
            if p_tags and len(p_tags) > 0:
                # First <p> without class is usually the description
                return clean_text(p_tags[0].text)
        return None

    def _extract_category(self, soup: BeautifulSoup) -> str:
        """Extract book category from breadcrumb."""
        breadcrumb = soup.find('ul', class_='breadcrumb')
        if breadcrumb:
            # Category is the second-to-last breadcrumb item
            li_tags = breadcrumb.find_all('li')
            if len(li_tags) >= 3:
                category_link = li_tags[-2].find('a')
                if category_link:
                    return clean_text(category_link.text)
        return "Unknown"

    def _extract_prices(self, soup: BeautifulSoup) -> tuple[float, float]:
        """Extract prices (excluding and including tax)."""
        price_excl_tax = 0.0
        price_incl_tax = 0.0

        # Prices are in a table with class "table table-striped"
        table = soup.find('table', class_='table-striped')
        if table:
            rows = table.find_all('tr')
            for row in rows:
                th = row.find('th')
                td = row.find('td')

                if th and td:
                    header = clean_text(th.text)
                    value = clean_text(td.text)

                    if 'Price (excl. tax)' in header:
                        price_excl_tax = extract_price(value)
                    elif 'Price (incl. tax)' in header:
                        price_incl_tax = extract_price(value)

        return price_excl_tax, price_incl_tax

    def _extract_availability(self, soup: BeautifulSoup) -> tuple[str, int]:
        """Extract availability status and number available."""
        availability_text = "Unknown"
        num_available = 0

        # Availability is in the table
        table = soup.find('table', class_='table-striped')
        if table:
            rows = table.find_all('tr')
            for row in rows:
                th = row.find('th')
                td = row.find('td')

                if th and td:
                    header = clean_text(th.text)
                    value = clean_text(td.text)

                    if 'Availability' in header:
                        availability_text = value
                        num_available = extract_number_from_availability(value)
                        break

        return availability_text, num_available

    def _extract_num_reviews(self, soup: BeautifulSoup) -> int:
        """Extract number of reviews."""
        table = soup.find('table', class_='table-striped')
        if table:
            rows = table.find_all('tr')
            for row in rows:
                th = row.find('th')
                td = row.find('td')

                if th and td:
                    header = clean_text(th.text)
                    value = clean_text(td.text)

                    if 'Number of reviews' in header:
                        try:
                            return int(value)
                        except ValueError:
                            return 0

        return 0

    def _extract_rating(self, soup: BeautifulSoup) -> str:
        """Extract star rating."""
        # Rating is in a <p> tag with class "star-rating [Rating]"
        rating_p = soup.find('p', class_='star-rating')
        if rating_p:
            # The rating is in the class name, e.g., "star-rating Three"
            classes = rating_p.get('class', [])
            for cls in classes:
                rating = normalize_rating(cls)
                if rating:
                    return rating

        return BookRating.THREE  # Default to Three if not found

    def _extract_image_url(self, soup: BeautifulSoup) -> str:
        """Extract book cover image URL."""
        img_tag = soup.find('img')
        if img_tag and img_tag.get('src'):
            relative_url = img_tag['src']
            # Image URLs are relative, make them absolute
            absolute_url = make_absolute_url(self.base_url, relative_url)
            return absolute_url

        return ""