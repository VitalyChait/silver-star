Silver Star Frontend (MVP)

A minimal Next.js frontend for the Silver Star job board MVP.

Quickstart
- npm install
- npm run dev
- Open http://localhost:3000

During development, API requests to `/api/*` rewrite to the backend on `http://localhost:8000`.

Notes
- The homepage lists jobs from GET /api/jobs/ and supports a simple keyword search.
- Create jobs via the backend API (requires auth) or seed script later.
