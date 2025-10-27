
# AI Job Agent Server

This FastAPI server wraps your **IntentCollectorTool** and **JobFetchersTool** so you can:
- Collect job-search intent from a conversational answer
- Fetch and rank jobs from allowed sources (RSS/APIs in your tool)

## Endpoints

### `GET /health`
Basic readiness check.

### `POST /intent`
Collect structured intent.

**Body:**
```json
{ "user_responses": "I'm looking for a senior iOS AR role, remote or Boston, $180k+, RealityKit/ARKit." }
```

**Response:**
```json
{
  "intent_json": { "...": "structured intent from your tool" },
  "raw": "{...original JSON string from tool...}"
}
```

### `POST /search`
Run job fetching/ranking on an intent.

**Body (intent as JSON object or string):**
```json
{
  "intent_json": { "...": "the intent JSON produced by /intent" }
}
```

**Response:**
Your tool's ranked job list (top 50 capped).

### `POST /run`
Convenience: do both steps at once.

**Body:**
```json
{ "user_responses": "Senior iOS AR, remote US, salary 170k-220k" }
```

**Response:**
Contains both the `intent_json` and the `results` from JobFetchers.

## Run Locally (uv)

```bash
# From the backend root (code/backend)
uv sync --extra craigslist

# In this folder
cd scrapers/craigslist
uv run uvicorn server:app --reload --port 8000
```

Open http://127.0.0.1:8000/docs for interactive Swagger UI.

## Notes

- The provided **JobFetchersTool** uses placeholder RSS/API URLs. Replace with real, allowed sources or partner APIs.
- Stay compliant with each site's Terms of Use. Avoid automated crawling of prohibited sites.
- For Craigslist, consider user-authorized email alerts ingestion rather than scraping.
