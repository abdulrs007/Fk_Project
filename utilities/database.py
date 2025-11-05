"""MongoDB database connection and utilities."""
import hashlib
import json
from typing import Optional, List, Dict, Any
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
from pymongo import IndexModel, ASCENDING, DESCENDING
from loguru import logger

from utilities.config import settings
from utilities.models import Book, ChangeLog, CrawlCheckpoint, ChangeType


class Database:
    """
    MongoDB database manager using async motor driver.

    **MongoDB Basics for Beginners:**
    - MongoDB stores data as JSON-like "documents" (dictionaries in Python)
    - A "collection" is like a table (e.g., "books" collection)
    - Each document has a unique "_id" field (auto-generated)
    - No fixed schema - documents can have different fields
    - "Indexes" speed up queries (like database indexes)
    """

    def __init__(self):
        """Initialize database connection."""
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[AsyncIOMotorDatabase] = None

    async def connect(self):
        """
        Connect to MongoDB and create indexes.

        **What are indexes?**
        Indexes make queries faster by creating a sorted lookup table.
        Without indexes, MongoDB scans every document.
        With indexes, it jumps directly to matching documents.
        """
        try:
            # Create async MongoDB client
            self.client = AsyncIOMotorClient(settings.mongodb_uri)
            self.db = self.client[settings.mongodb_db_name]

            # Test connection
            await self.client.admin.command('ping')
            logger.info(f"Connected to MongoDB: {settings.mongodb_db_name}")

            # Create collections and indexes
            await self._create_indexes()

        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            raise

    async def disconnect(self):
        """Close database connection."""
        if self.client:
            self.client.close()
            logger.info("Disconnected from MongoDB")

    async def _create_indexes(self):
        """
        Create indexes for efficient querying.

        **Why these indexes?**
        - source_url: Find books by URL (for deduplication)
        - category: Filter books by category (API endpoint)
        - price_incl_tax: Sort/filter by price (API endpoint)
        - rating: Filter by rating (API endpoint)
        - crawl_timestamp: Sort by crawl date
        - content_hash: Quick change detection
        """
        books_collection = self.db.books

        # Create indexes for books collection
        indexes = [
            IndexModel([("source_url", ASCENDING)], unique=True),  # Unique constraint on URL
            IndexModel([("category", ASCENDING)]),
            IndexModel([("price_incl_tax", ASCENDING)]),
            IndexModel([("rating", ASCENDING)]),
            IndexModel([("num_reviews", DESCENDING)]),
            IndexModel([("crawl_timestamp", DESCENDING)]),
            IndexModel([("content_hash", ASCENDING)]),
            IndexModel([("name", ASCENDING)]),  # Text search on name
        ]

        await books_collection.create_indexes(indexes)
        logger.info("Created indexes for 'books' collection")

        # Create indexes for changelog collection
        changelog_collection = self.db.changelog
        changelog_indexes = [
            IndexModel([("book_id", ASCENDING)]),
            IndexModel([("change_type", ASCENDING)]),
            IndexModel([("change_timestamp", DESCENDING)]),
        ]

        await changelog_collection.create_indexes(changelog_indexes)
        logger.info("Created indexes for 'changelog' collection")

        # Create index for checkpoints
        checkpoint_collection = self.db.checkpoints
        checkpoint_indexes = [
            IndexModel([("checkpoint_id", ASCENDING)], unique=True),
        ]

        await checkpoint_collection.create_indexes(checkpoint_indexes)
        logger.info("Created indexes for 'checkpoints' collection")

    @property
    def books(self) -> AsyncIOMotorCollection:
        """Get books collection."""
        return self.db.books

    @property
    def changelog(self) -> AsyncIOMotorCollection:
        """Get changelog collection."""
        return self.db.changelog

    @property
    def checkpoints(self) -> AsyncIOMotorCollection:
        """Get checkpoints collection."""
        return self.db.checkpoints

    # ========== Book Operations ==========

    async def insert_book(self, book: Book) -> str:
        """
        Insert a new book into the database.

        Returns: MongoDB _id of the inserted document
        """
        book_dict = book.model_dump(by_alias=True, exclude={"id"})
        result = await self.books.insert_one(book_dict)
        logger.debug(f"Inserted book: {book.name} (ID: {result.inserted_id})")
        return str(result.inserted_id)

    async def upsert_book(self, book: Book) -> tuple[str, bool]:
        """
        Insert or update a book (upsert = update + insert).

        **How it works:**
        - If book with same source_url exists, update it
        - If not, insert as new book

        Returns: (book_id, is_new) where is_new=True if inserted
        """
        book_dict = book.model_dump(by_alias=True, exclude={"id"})

        result = await self.books.update_one(
            {"source_url": book.source_url},
            {"$set": book_dict},
            upsert=True  # Create if doesn't exist
        )

        book_id = str(result.upserted_id) if result.upserted_id else await self.get_book_id_by_url(book.source_url)
        is_new = result.upserted_id is not None

        return book_id, is_new

    async def get_book_by_url(self, source_url: str) -> Optional[Book]:
        """Get a book by its source URL."""
        book_dict = await self.books.find_one({"source_url": source_url})
        if book_dict:
            book_dict["_id"] = str(book_dict["_id"])
            return Book(**book_dict)
        return None

    async def get_book_id_by_url(self, source_url: str) -> Optional[str]:
        """Get just the book ID by URL (faster than fetching full document)."""
        result = await self.books.find_one({"source_url": source_url}, {"_id": 1})
        return str(result["_id"]) if result else None

    async def get_all_books(
        self,
        skip: int = 0,
        limit: int = 50,
        category: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        rating: Optional[str] = None,
        sort_by: str = "crawl_timestamp",
        sort_order: int = DESCENDING
    ) -> List[Dict[str, Any]]:
        """
        Get books with filtering, pagination, and sorting.

        **MongoDB Query Operators:**
        - $gte: greater than or equal
        - $lte: less than or equal
        """
        query = {}

        # Build filter query
        if category:
            query["category"] = category

        if min_price is not None or max_price is not None:
            query["price_incl_tax"] = {}
            if min_price is not None:
                query["price_incl_tax"]["$gte"] = min_price
            if max_price is not None:
                query["price_incl_tax"]["$lte"] = max_price

        if rating:
            query["rating"] = rating

        # Execute query with pagination and sorting
        cursor = self.books.find(query).skip(skip).limit(limit).sort(sort_by, sort_order)

        books = []
        async for book in cursor:
            book["_id"] = str(book["_id"])
            books.append(book)

        return books

    async def count_books(self, query: Optional[Dict] = None) -> int:
        """Count total books matching query."""
        return await self.books.count_documents(query or {})

    # ========== ChangeLog Operations ==========

    async def insert_change(self, change: ChangeLog) -> str:
        """Insert a change log entry."""
        change_dict = change.model_dump(by_alias=True, exclude={"id"})
        result = await self.changelog.insert_one(change_dict)
        logger.info(f"Logged change: {change.change_type} for book {change.book_name}")
        return str(result.inserted_id)

    async def get_recent_changes(
        self,
        limit: int = 100,
        change_type: Optional[ChangeType] = None,
        since: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Get recent changes with optional filtering."""
        query = {}

        if change_type:
            query["change_type"] = change_type

        if since:
            query["change_timestamp"] = {"$gte": since}

        cursor = self.changelog.find(query).sort("change_timestamp", DESCENDING).limit(limit)

        changes = []
        async for change in cursor:
            change["_id"] = str(change["_id"])
            changes.append(change)

        return changes

    # ========== Checkpoint Operations ==========

    async def save_checkpoint(self, checkpoint: CrawlCheckpoint):
        """Save or update a crawl checkpoint."""
        checkpoint_dict = checkpoint.model_dump(by_alias=True, exclude={"id"})

        await self.checkpoints.update_one(
            {"checkpoint_id": checkpoint.checkpoint_id},
            {"$set": checkpoint_dict},
            upsert=True
        )

        logger.debug(f"Saved checkpoint: {checkpoint.checkpoint_id}")

    async def get_checkpoint(self, checkpoint_id: str = "main_crawl") -> Optional[CrawlCheckpoint]:
        """Get a saved checkpoint."""
        checkpoint_dict = await self.checkpoints.find_one({"checkpoint_id": checkpoint_id})

        if checkpoint_dict:
            checkpoint_dict["_id"] = str(checkpoint_dict["_id"])
            return CrawlCheckpoint(**checkpoint_dict)

        return None

    # ========== Utility Functions ==========

    @staticmethod
    def compute_content_hash(book: Book) -> str:
        """
        Compute a hash of book content for change detection.

        **How it works:**
        - Takes fields that might change (price, availability)
        - Converts to JSON string
        - Creates SHA256 hash
        - Fast comparison: if hash differs, content changed
        """
        content = {
            "name": book.name,
            "price_incl_tax": book.price_incl_tax,
            "price_excl_tax": book.price_excl_tax,
            "availability": book.availability,
            "num_available": book.num_available,
            "num_reviews": book.num_reviews,
            "rating": book.rating,
        }

        content_str = json.dumps(content, sort_keys=True)
        return hashlib.sha256(content_str.encode()).hexdigest()


# Singleton database instance
db = Database()