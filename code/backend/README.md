# SilverStar Backend Server

FastAPI backend server for the SilverStar job application platform.

## Features

- User authentication (register/login)
- Job management (CRUD operations)
- AI-powered job recommendations via chatbot
- Job scraping from USAJOBS
- Voice interaction support

## Setup

1. Install dependencies (uv):
```bash
uv sync
```

Optional: install extras for scrapers
```bash
# Craigslist tooling
uv sync --extra craigslist
# USAJOBS tooling
uv sync --extra usajobs
```

2. Configure LLM API keys:
```bash
cp app/llm/llm_config_example app/llm/.llm_config
# Edit app/llm/.llm_config with your API keys
```

3. Initialize the database with sample jobs:
```bash
uv run python populate_jobs.py
```

## Running the Server

Start the server using the provided script:
```bash
uv run python start_server.py
```

Or run directly with uvicorn:
```bash
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

## API Endpoints

### Authentication
- `POST /api/register` - Register a new user
- `POST /api/login` - Login user and get token
- `GET /api/profile` - Get current user profile (requires auth)

### Jobs
- `GET /api/jobs` - List all jobs
- `POST /api/jobs` - Create a new job (requires auth)
- `GET /api/jobs/{id}` - Get specific job
- `PATCH /api/jobs/{id}` - Update a job (requires auth)
- `DELETE /api/jobs/{id}` - Delete a job (requires auth)

### Chatbot
- `POST /api/chatbot/chat` - Send message to chatbot
- `POST /api/chatbot/voice` - Send voice message to chatbot
- `POST /api/chatbot/reset` - Reset chatbot conversation

### Job Scraper (Admin only)
- `POST /api/job-scraper/scrape-usajobs` - Scrape jobs from USAJOBS
- `GET /api/job-scraper/scraping-status` - Get scraping status

## Frontend

The frontend is located in `../../frontend/` and consists of:

1. `silverstar.html` - Main landing page with authentication
2. `chatbot.html` - Chatbot interface for job search

To run the frontend, simply open the HTML files in a browser or serve them with a web server.

## Development

The server supports hot reloading during development. Changes to Python files will automatically restart the server.

## Database

The application uses SQLAlchemy with SQLite by default. The database file is `data.db` in the server directory.
