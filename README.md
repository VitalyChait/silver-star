# silver-star

<img width="1088" height="960" alt="silver_star_logo" src="https://github.com/user-attachments/assets/1961ad11-1dee-4fc5-941d-17306c309d38" />


This repo contains the Silver Star MVP: a simple FastAPI backend and a Next.js frontend for a job board connecting senior professionals with meaningful work.

## Features

- Job board with search functionality
- User authentication
- **AI-powered chatbot for job recommendations** (NEW!)
- Voice interaction with the chatbot
- Personalized job matching based on candidate profile

## Run the App (Local Dev)

Prerequisites
- Python 3.11+
- Node.js 18+

### 1) Backend API (FastAPI)

Location: `code/backend/server`

Steps
1. Create a virtual environment and install dependencies
   - `cd code/backend/server`
   - `python -m venv .venv && source .venv/bin/activate` (Use python3 if python command does not work)
   - `pip install -r requirements.txt`
2. (Optional) Configure env vars
   - Copy `.env.example` to `.env` and adjust if needed
   - Default DB is SQLite: `sqlite:///./data.db`
3. Configure LLM settings
   - Create `code/backend/llm/.llm_config` with your API keys (see `code/backend/llm/README.md`)
4. Start the server
   - `uvicorn app.main:app --reload --port 8000`
5. Verify
   - API docs: `http://localhost:8000/docs`
   - Health: `http://localhost:8000/health`

Common API endpoints
- `POST /api/auth/register` — Register user `{email, password}`
- `POST /api/auth/token` — Get JWT (OAuth2 password)
- `GET /api/jobs/` — List/search jobs (`?q=keyword`)
- `POST /api/jobs/` — Create job (requires Bearer token)
- `POST /api/chatbot/chat` — Send text message to chatbot
- `POST /api/chatbot/voice` — Send voice message to chatbot

### 2) Frontend (Next.js)

Location: `code/frontend`

Steps
1. Install deps and run dev server
   - Open a new terminal
   - `cd code/frontend`
   - `npm install`
   - `npm run dev`
2. Open the app
   - `http://localhost:3000`
   - Chatbot: `http://localhost:3000/chatbot`

Notes
- Frontend rewrites `/api/*` to the backend at `http://localhost:8000/*` during dev (see `code/frontend/next.config.js`).
- Start backend first, then the frontend.

### 3) Chatbot Feature

The AI-powered chatbot helps candidates find suitable jobs by:
1. Collecting candidate information (name, location, job preferences, skills, availability)
2. Providing personalized job recommendations based on their profile
3. Supporting both text and voice interactions

The chatbot uses Google's Gemini AI for natural language processing and job matching.

Troubleshooting
- 

## Project Docs
- Roadmap: `non-code/roadmap.md`
- Stack proposal (optional A): `non-code/arch/stack/optional_a.html`
- LLM Module: `code/backend/llm/README.md`

## Subproject READMEs
- Backend: `code/backend/server/README.md`
- Frontend: `code/frontend/README.md`
