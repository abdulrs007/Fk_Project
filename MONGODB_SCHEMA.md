## MongoDB Schema Documentation

This document describes the MongoDB collections and their schemas used in the Books Crawler project.

### Database Overview

**Database Name**: `books_crawler` (configurable via `.env`)

**Collections**:
1. `books` - Stores book data
2. `changelog` - Tracks changes over time
3. `checkpoints` - Stores crawler progress

---

### Collection: `books`

Stores detailed information about each book crawled from the website.

#### Schema

```json
{
  "_id": ObjectId,              // Auto-generated MongoDB ID
  "name": String,               // Book title (required)
  "description": String | null, // Book description
  "category": String,           // Book category (required)
  "price_excl_tax": Number,     // Price excluding tax (≥ 0)
  "price_incl_tax": Number,     // Price including tax (≥ 0)
  "availability": String,       // Availability text (e.g., "In stock (22 available)")
  "num_available": Integer,     // Number of items in stock (≥ 0)
  "num_reviews": Integer,       // Number of reviews (≥ 0)
  "rating": String,             // Rating: "One", "Two", "Three", "Four", or "Five"
  "image_url": String,          // URL to book cover image
  "source_url": String,         // Original URL of book page (unique)
  "crawl_timestamp": ISODate,   // When this book was last crawled
  "crawl_status": String,       // Status: "success", "failed", or "partial"
  "raw_html": String | null,    // Raw HTML snapshot of book page
  "content_hash": String        // SHA256 hash for change detection
}
```

#### Sample Document

```json
{
  "_id": ObjectId("673a5f8a1e4d2c1a2b3c4d5e"),
  "name": "A Light in the Attic",
  "description": "It's hard to imagine a world without A Light in the Attic. This now-classic collection of poetry and drawings from Shel Silverstein celebrates its 20th anniversary...",
  "category": "Poetry",
  "price_excl_tax": 51.77,
  "price_incl_tax": 51.77,
  "availability": "In stock (22 available)",
  "num_available": 22,
  "num_reviews": 0,
  "rating": "Three",
  "image_url": "https://books.toscrape.com/media/cache/2c/da/2cdad67c44b002e7ead0cc35693c0e8b.jpg",
  "source_url": "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html",
  "crawl_timestamp": ISODate("2025-11-05T10:15:30.123Z"),
  "crawl_status": "success",
  "raw_html": "<!DOCTYPE html><html>...",
  "content_hash": "a3f2d8e1b4c5..."
}
```

#### Indexes

```javascript
// Unique index on source_url for deduplication
db.books.createIndex({ "source_url": 1 }, { unique: true });

// Indexes for filtering and sorting
db.books.createIndex({ "category": 1 });
db.books.createIndex({ "price_incl_tax": 1 });
db.books.createIndex({ "rating": 1 });
db.books.createIndex({ "num_reviews": -1 });
db.books.createIndex({ "crawl_timestamp": -1 });
db.books.createIndex({ "content_hash": 1 });
db.books.createIndex({ "name": 1 });
```

#### Queries

**Find all books in a category:**
```javascript
db.books.find({ category: "Fiction" })
```

**Find books in price range:**
```javascript
db.books.find({
  price_incl_tax: { $gte: 10, $lte: 50 }
})
```

**Find highly rated books:**
```javascript
db.books.find({ rating: "Five" }).sort({ num_reviews: -1 })
```

**Count books by category:**
```javascript
db.books.aggregate([
  { $group: { _id: "$category", count: { $sum: 1 } } },
  { $sort: { count: -1 } }
])
```

---

### Collection: `changelog`

Tracks all detected changes (new books, price changes, availability changes).

#### Schema

```json
{
  "_id": ObjectId,            // Auto-generated MongoDB ID
  "book_id": String,          // MongoDB _id of the book (as string)
  "book_name": String,        // Name of the book (for quick reference)
  "change_type": String,      // Type: "new_book", "price_change", "availability_change", "content_change", "deleted"
  "change_timestamp": ISODate,// When the change was detected
  "old_value": Object | null, // Previous value(s)
  "new_value": Object | null, // New value(s)
  "description": String       // Human-readable description
}
```

#### Sample Documents

**New Book:**
```json
{
  "_id": ObjectId("673a6001f1e2d3c4a5b6c7d8"),
  "book_id": "673a5f8a1e4d2c1a2b3c4d5e",
  "book_name": "The Mysterious Affair at Styles",
  "change_type": "new_book",
  "change_timestamp": ISODate("2025-11-05T14:30:00.000Z"),
  "old_value": null,
  "new_value": {
    "name": "The Mysterious Affair at Styles",
    "price": 24.99
  },
  "description": "New book added: The Mysterious Affair at Styles"
}
```

**Price Change:**
```json
{
  "_id": ObjectId("673a6002f2e3d4c5a6b7c8d9"),
  "book_id": "673a5f8a1e4d2c1a2b3c4d5e",
  "book_name": "A Light in the Attic",
  "change_type": "price_change",
  "change_timestamp": ISODate("2025-11-06T02:15:00.000Z"),
  "old_value": {
    "price_incl_tax": 51.77
  },
  "new_value": {
    "price_incl_tax": 45.99
  },
  "description": "Price decreased from £51.77 to £45.99"
}
```

**Availability Change:**
```json
{
  "_id": ObjectId("673a6003f3e4d5c6a7b8c9da"),
  "book_id": "673a5f8a1e4d2c1a2b3c4d5e",
  "book_name": "A Light in the Attic",
  "change_type": "availability_change",
  "change_timestamp": ISODate("2025-11-06T02:15:00.000Z"),
  "old_value": {
    "num_available": 22,
    "availability": "In stock (22 available)"
  },
  "new_value": {
    "num_available": 15,
    "availability": "In stock (15 available)"
  },
  "description": "Availability changed from 22 to 15"
}
```

#### Indexes

```javascript
// Index for querying changes by book
db.changelog.createIndex({ "book_id": 1 });

// Index for filtering by change type
db.changelog.createIndex({ "change_type": 1 });

// Index for sorting by timestamp
db.changelog.createIndex({ "change_timestamp": -1 });
```

#### Queries

**Get all changes for a book:**
```javascript
db.changelog.find({ book_id: "673a5f8a1e4d2c1a2b3c4d5e" })
  .sort({ change_timestamp: -1 })
```

**Get recent price changes:**
```javascript
db.changelog.find({ change_type: "price_change" })
  .sort({ change_timestamp: -1 })
  .limit(50)
```

**Get changes in last 24 hours:**
```javascript
const yesterday = new Date(Date.now() - 24*60*60*1000);
db.changelog.find({
  change_timestamp: { $gte: yesterday }
})
```

---

### Collection: `checkpoints`

Stores crawler progress to enable resuming from interruptions.

#### Schema

```json
{
  "_id": ObjectId,               // Auto-generated MongoDB ID
  "checkpoint_id": String,       // Identifier (e.g., "main_crawl") - unique
  "last_page_url": String,       // Last successfully crawled catalog page
  "last_book_url": String | null,// Last successfully crawled book URL
  "total_books_crawled": Integer,// Total books crawled so far (≥ 0)
  "timestamp": ISODate,          // When checkpoint was created
  "status": String               // Status: "success", "failed", or "partial"
}
```

#### Sample Document

```json
{
  "_id": ObjectId("673a6004f4e5d6c7a8b9cada"),
  "checkpoint_id": "main_crawl",
  "last_page_url": "https://books.toscrape.com/catalogue/page-15.html",
  "last_book_url": "https://books.toscrape.com/catalogue/soumission_998/index.html",
  "total_books_crawled": 750,
  "timestamp": ISODate("2025-11-05T10:45:30.000Z"),
  "status": "partial"
}
```

#### Indexes

```javascript
// Unique index on checkpoint_id
db.checkpoints.createIndex({ "checkpoint_id": 1 }, { unique: true });
```

#### Queries

**Get the latest checkpoint:**
```javascript
db.checkpoints.findOne({ checkpoint_id: "main_crawl" })
```

**Update checkpoint:**
```javascript
db.checkpoints.updateOne(
  { checkpoint_id: "main_crawl" },
  {
    $set: {
      last_page_url: "https://books.toscrape.com/catalogue/page-20.html",
      total_books_crawled: 1000,
      timestamp: new Date(),
      status: "success"
    }
  },
  { upsert: true }
)
```

---

## Database Operations

### Connect to MongoDB

```bash
# Local MongoDB
mongo

# Use the database
use books_crawler
```

### Useful Commands

**Show all collections:**
```javascript
show collections
```

**Count documents:**
```javascript
db.books.countDocuments()
db.changelog.countDocuments()
```

**Get collection stats:**
```javascript
db.books.stats()
```

**View indexes:**
```javascript
db.books.getIndexes()
```

**Drop collection (careful!):**
```javascript
db.changelog.drop()
```

**Backup database:**
```bash
mongodump --db books_crawler --out ./backup
```

**Restore database:**
```bash
mongorestore --db books_crawler ./backup/books_crawler
```

---

## Change Detection Strategy

The system uses **content hashing** for efficient change detection:

1. **Initial Crawl**:
   - Scrape book data
   - Compute `content_hash` from key fields (price, availability, rating)
   - Store in database

2. **Subsequent Crawls**:
   - Scrape current data
   - Compute new `content_hash`
   - Compare with stored hash
   - If different → fetch old record → compare fields → log specific changes

3. **Content Hash Calculation**:
```python
import hashlib
import json

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
content_hash = hashlib.sha256(content_str.encode()).hexdigest()
```

---

## Performance Considerations

### Indexes
- Indexes speed up queries but slow down writes
- Current indexes are optimized for API queries
- Monitor slow queries with: `db.setProfilingLevel(2)`

### Upsert Operations
- Use `upsert=True` to avoid checking if document exists
- Significantly faster than find-then-insert pattern

### Bulk Operations
For inserting many books:
```python
books_data = [book.model_dump() for book in books_list]
db.books.insert_many(books_data, ordered=False)
```

### Connection Pooling
Motor (async MongoDB driver) handles connection pooling automatically.

---

## MongoDB Best Practices

1. **Always use indexes** for frequently queried fields
2. **Use projection** to fetch only needed fields
3. **Avoid large documents** (current max ~16MB)
4. **Use TTL indexes** for auto-expiring data (if needed)
5. **Enable authentication** in production
6. **Regular backups** using mongodump
7. **Monitor performance** with MongoDB Atlas/Ops Manager

---

## Scaling Considerations

### When to Scale

- **10K+ books**: Current setup handles easily
- **100K+ books**: Consider compound indexes, sharding prep
- **1M+ books**: MongoDB sharding, read replicas
- **10M+ books**: Horizontal scaling, distributed architecture

### Optimization Tips

1. **Compound Indexes** for multi-field queries:
   ```javascript
   db.books.createIndex({ category: 1, price_incl_tax: 1 })
   ```

2. **Covered Queries** (query uses only indexed fields):
   ```javascript
   db.books.find(
     { category: "Fiction" },
     { name: 1, price_incl_tax: 1, _id: 0 }
   )
   ```

3. **Aggregation Pipeline** for complex queries:
   ```javascript
   db.books.aggregate([
     { $match: { category: "Fiction" } },
     { $group: { _id: "$rating", avg_price: { $avg: "$price_incl_tax" } } }
   ])
   ```

---

**End of MongoDB Schema Documentation**