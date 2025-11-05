# Quick Start Guide

This guide will help you get the Books Crawler up and running quickly.

## Step-by-Step Setup

### 1. Install MongoDB

Choose one option:

**Option A: MongoDB Atlas (Cloud - Easiest)**
1. Go to [mongodb.com/cloud/atlas/register](https://www.mongodb.com/cloud/atlas/register)
2. Create free account
3. Create a free cluster (M0)
4. Click "Connect" → "Connect your application"
5. Copy the connection string (looks like: `mongodb+srv://username:password@cluster.mongodb.net/`)
6. Update `.env` file:
   ```
   MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/
   ```

**Option B: Local Installation**
1. Download from [mongodb.com/try/download/community](https://www.mongodb.com/try/download/community)
2. Install and start MongoDB
3. No changes needed in `.env` (already configured for local)

**Option C: Docker**
```bash
docker run -d -p 27017:27017 --name mongodb mongo:latest
```

### 2. Setup Python Environment

```bash
# Navigate to project
cd D:\FK_PROJECT

# Create virtual environment
python -m venv .venv

# Activate it (Windows)
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Verify Installation

```bash
# Test configuration
python utilities/config.py
```

You should see configuration loaded successfully.

### 4. Run Your First Crawl

```bash
# Start the crawler (this will take 2-5 minutes)
python crawler/main.py
```

What happens:
- Connects to MongoDB
- Creates database and collections
- Crawls ~1000 books from books.toscrape.com
- Shows progress in real-time
- Saves checkpoints (so you can resume if interrupted)

**Expected Output:**
```
2025-11-05 10:15:30 | INFO     | Connecting to MongoDB...
2025-11-05 10:15:31 | INFO     | Connected to MongoDB: books_crawler
2025-11-05 10:15:31 | INFO     | Starting book scraping...
2025-11-05 10:15:32 | INFO     | Scraping catalog page 1: https://books.toscrape.com/catalogue/page-1.html
2025-11-05 10:15:33 | INFO     | Found 20 books on page 1
2025-11-05 10:15:35 | INFO     | Page 1 completed. Total books: 20
...
2025-11-05 10:20:45 | INFO     | Scraping completed!
2025-11-05 10:20:45 | INFO     | Total books crawled: 1000
```

### 5. Start the API

Open a **new terminal** (keep crawler terminal for logs):

```bash
# Activate virtual environment
.venv\Scripts\activate

# Start API server
python api/main.py
```

API will start at: `http://localhost:8001`

**Visit in browser:**
- Interactive docs: `http://localhost:8001/docs`
- Health check: `http://localhost:8001/api/v1/health`

### 6. Test the API

#### In Browser (Swagger UI)

1. Go to `http://localhost:8001/docs`
2. Click "Authorize" button (top right)
3. Enter API key: `dev-api-key-12345`
4. Click "Authorize" then "Close"
5. Try the `/api/v1/books` endpoint:
   - Click "Try it out"
   - Click "Execute"
   - See results!

#### Using curl (Command Line)

```bash
# Get health status
curl http://localhost:8001/api/v1/health

# List books (with API key)
curl -H "X-API-Key: dev-api-key-12345" http://localhost:8001/api/v1/books

# Get books in a category
curl -H "X-API-Key: dev-api-key-12345" "http://localhost:8001/api/v1/books?category=Fiction&page_size=5"

# Get all categories
curl -H "X-API-Key: dev-api-key-12345" http://localhost:8001/api/v1/categories
```

#### Using Python

Create `test_api.py`:

```python
import requests

API_URL = "http://localhost:8001/api/v1"
API_KEY = "dev-api-key-12345"
headers = {"X-API-Key": API_KEY}

# Get first 5 books
response = requests.get(f"{API_URL}/books", headers=headers, params={"page_size": 5})
data = response.json()

print(f"Total books: {data['total']}")
print(f"\nFirst {len(data['books'])} books:")
for book in data['books']:
    print(f"  - {book['name']}: £{book['price_incl_tax']} ({book['rating']} stars)")
```

Run it:
```bash
python test_api.py
```

### 7. Run Change Detection

This will re-crawl and detect any changes:

```bash
# Run immediately (don't wait for scheduled time)
python scheduler/main.py --now
```

What happens:
- Crawls the site again
- Compares with existing data
- Detects new books (if any)
- Generates a report in `reports/` folder
- Logs changes to database

**View changes via API:**
```bash
curl -H "X-API-Key: dev-api-key-12345" http://localhost:8001/api/v1/changes
```

### 8. Schedule Automatic Crawls

To run daily crawls automatically:

```bash
# Start scheduler (runs daily at 2:00 AM)
python scheduler/main.py
```

Leave this running in background. It will:
- Run crawl daily at configured time
- Detect and log changes
- Generate daily reports
- Keep running until you stop it (Ctrl+C)

---

## Common Issues

### "Failed to connect to MongoDB"

**Atlas Users:**
1. Check internet connection
2. Whitelist your IP in Atlas dashboard: Network Access → Add IP Address → Add Current IP
3. Verify connection string in `.env`

**Local Users:**
1. Make sure MongoDB is running: `mongod --version`
2. Start MongoDB service:
   - Windows: Services → MongoDB → Start
   - Mac: `brew services start mongodb-community`
   - Linux: `sudo systemctl start mongod`

### "Module not found" errors

Make sure virtual environment is activated:
```bash
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Mac/Linux
```

Then reinstall:
```bash
pip install -r requirements.txt
```

### API returns 403 Forbidden

You forgot the API key! Add header:
```bash
-H "X-API-Key: dev-api-key-12345"
```

### Crawler is slow

- Check your internet speed
- Increase concurrent requests in `.env`:
  ```
  CRAWLER_CONCURRENT_REQUESTS=20
  ```
- Note: Too many concurrent requests may get you rate-limited

---

## What to Try Next

### 1. Test Filtering

```bash
# Books in specific category
curl -H "X-API-Key: dev-api-key-12345" \
  "http://localhost:8001/api/v1/books?category=Poetry"

# Books in price range
curl -H "X-API-Key: dev-api-key-12345" \
  "http://localhost:8001/api/v1/books?min_price=10&max_price=30"

# Highly rated books
curl -H "X-API-Key: dev-api-key-12345" \
  "http://localhost:8001/api/v1/books?rating=Five"
```

### 2. View MongoDB Data

If you installed MongoDB locally:

```bash
# Open MongoDB shell
mongosh

# Use the database
use books_crawler

# Count books
db.books.countDocuments()

# View first book
db.books.findOne()

# List all categories
db.books.distinct("category")

# Exit
exit
```

### 3. View Logs

```bash
# Real-time logs
tail -f logs/crawler.log

# Or on Windows with PowerShell
Get-Content logs/crawler.log -Wait
```

### 4. Run Tests

```bash
pytest
```

### 5. Generate API Documentation

Already available at:
- Swagger: `http://localhost:8001/docs`
- ReDoc: `http://localhost:8001/redoc`

---

## Development Workflow

**Typical workflow:**

1. **Morning**: Start API server
   ```bash
   python api/main.py
   ```

2. **As needed**: Run crawler manually
   ```bash
   python crawler/main.py
   ```

3. **Check for changes**:
   ```bash
   python scheduler/main.py --now
   ```

4. **View data**: Use Swagger UI at `http://localhost:8001/docs`

5. **For production**: Let scheduler run automatically
   ```bash
   python scheduler/main.py
   ```

---

## Next Steps

1.  Read `README.md` for complete documentation
2.  Check `MONGODB_SCHEMA.md` to understand the database
3.  Explore API at `http://localhost:8001/docs`
4.  Review code in `crawler/`, `api/`, and `scheduler/`
5.  Customize `.env` configuration

