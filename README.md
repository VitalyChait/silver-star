# SilverStar

SilverStar is a job application platform that connects experienced professionals with suitable job opportunities. The platform features an AI-powered chatbot that helps candidates find relevant positions based on their skills, preferences, and availability.

## Features

- User authentication and profile management
- AI-powered job recommendations via chatbot
- Voice interaction support for the chatbot
- Job scraping from USAJOBS
- Modern, responsive UI with custom star cursor

## Quick Start (uv)

We use the uv Python environment manager for dependency management and running commands.

First, install uv if you don't have it:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then use the automated setup script:

```bash
# Clone the repository
git clone <repository-url>
cd silver-star

# Run the setup and start script (uses uv)
./setup_and_run.sh
```

This single script will:
1. Install all Python dependencies
2. Set up the LLM configuration file
3. Initialize the database with sample jobs
4. Start both the backend and frontend servers
5. Clean up any unnecessary files

## Manual Setup (uv)

If you prefer to set up manually with uv:

### 1. Backend Setup

```bash
cd code/backend

# Install dependencies from pyproject.toml
uv sync

# Configure LLM API keys
cp app/llm/llm_config_example app/llm/.llm_config
# Edit app/llm/.llm_config with your actual API keys

# Initialize database
uv run python populate_jobs.py

# Start the server
uv run python start_server.py
```

### 2. Frontend

The frontend consists of static HTML files that can be served by any web server. To run a simple server:

```bash
cd code/frontend
uv run python -m http.server 3000
```

## Accessing the Application

Once running, you can access:

- Main page: http://localhost:3000/silverstar.html
- Chatbot: http://localhost:3000/chatbot.html
- API documentation: http://localhost:8000/docs

## Configuration

### LLM Configuration

The application uses Google's Gemini API for the chatbot functionality. You'll need to:

1. Get an API key from [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Edit `code/backend/app/llm/.llm_config` and replace `your_gemini_api_key_here` with your actual API key

### Database

The application uses SQLite by default, with the database file stored at `code/backend/data.db`. The database is automatically initialized with sample jobs on first run.

## Architecture

- **Backend**: FastAPI with SQLAlchemy ORM
- **Frontend**: Vanilla HTML, CSS, and JavaScript
- **AI Integration**: Google Gemini API
- **Job Scraping**: USAJOBS API

## Development

The backend server supports hot reloading during development. Changes to Python files will automatically restart the server.

## License

This project is licensed under the terms specified in the [LICENSE](LICENSE) file.
