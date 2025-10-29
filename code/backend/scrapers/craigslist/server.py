
import json
import os
from typing import Any, Dict, Optional, Union

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from pathlib import Path
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from tools.intent_collector import IntentCollectorTool
from tools.job_fetchers import JobFetchersTool

BASE_DIR = Path(__file__).resolve().parent
INDEX_PATH = BASE_DIR / "index.html"



app = FastAPI(title="AI Job Agent Server", version="0.1.0")

# CORS (adjust origins as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------- Pydantic request/response models ----------

class IntentRequest(BaseModel):
    user_responses: str

class IntentResponse(BaseModel):
    intent_json: Dict[str, Any]
    raw: str

class SearchRequest(BaseModel):
    # Accept either a JSON object or a JSON string for intent_json
    intent_json: Union[Dict[str, Any], str]

class SearchResponse(BaseModel):
    status: str
    fetch_summary: Dict[str, Any]
    jobs_found: int
    jobs: Any
    search_criteria: Dict[str, Any]

class RunRequest(BaseModel):
    user_responses: str

class RunResponse(BaseModel):
    intent_json: Dict[str, Any]
    results: Optional[SearchResponse]

# ---------- Endpoints ----------


@app.get("/", response_class=HTMLResponse)
def home():
    if INDEX_PATH.exists():
        return INDEX_PATH.read_text(encoding="utf-8")
    # Fallback HTML if index.html is missing
    return HTMLResponse(
        "<!doctype html><meta charset='utf-8'><body>"
        "<h1>AI Job Agent</h1>"
        "<p>Missing <code>index.html</code> next to <code>server.py</code>.</p>"
        "</body>",
        status_code=200,
    )



@app.get("/health")
def health():
    return {"ok": True}

@app.post("/intent", response_model=IntentResponse)
def collect_intent(body: IntentRequest):
    tool = IntentCollectorTool()
    output = tool.run(user_responses=body.user_responses)
    try:
        intent_json = json.loads(output)
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail=f"IntentCollectorTool returned non-JSON: {output}")
    return {"intent_json": intent_json, "raw": output}

@app.post("/search", response_model=SearchResponse)
def search_jobs(body: SearchRequest):
    tool = JobFetchersTool()
    if isinstance(body.intent_json, dict):
        intent_str = json.dumps(body.intent_json)
    else:
        intent_str = body.intent_json

    output = tool.run(intent_json=intent_str)

    try:
        data = json.loads(output)
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail=f"JobFetchersTool returned non-JSON: {output}")

    # Minimal shape validation
    for key in ["status", "fetch_summary", "jobs_found", "jobs", "search_criteria"]:
        if key not in data:
            raise HTTPException(status_code=422, detail=f"Missing '{key}' in JobFetchersTool response")

    return data

@app.post("/run", response_model=RunResponse)
def run_pipeline(body: RunRequest):
    # Step 1: Collect intent
    ic_tool = IntentCollectorTool()
    ic_out = ic_tool.run(user_responses=body.user_responses)
    try:
        intent_json = json.loads(ic_out)
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail=f"IntentCollectorTool returned non-JSON: {ic_out}")

    # Step 2: Fetch & rank jobs
    jf_tool = JobFetchersTool()
    jf_out = jf_tool.run(intent_json=json.dumps(intent_json))

    try:
        results = json.loads(jf_out)
    except json.JSONDecodeError:
        raise HTTPException(status_code=422, detail=f"JobFetchersTool returned non-JSON: {jf_out}")

    return {"intent_json": intent_json, "results": results}

# Optional: local dev server
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=os.getenv("PYTHON_APP_PORT"))


INTENT_QUESTIONS = [
    "1) What roles or titles are you targeting? (e.g., 'Senior iOS Engineer', 'AR/Computer Vision')",
    "2) Your skills?",
    "4) Location preferences? (remote / hybrid / onsite + cities + radius)",
    "5) Work type? (contract / part-time)",
    "7) Industry focus? (e.g., XR, fintech, healthtech)",
    "8) Salary expectations? (min, currency)",
    "9) Max posting age? (e.g., last 14 days)",
    "10) Exclusions? (keywords, recruiters-only, unpaid, internship)"
]

INTENT_TEMPLATE = """
I'm looking for: <roles/titles>.
Must-have: <skills>.
Nice-to-have: <skills>.
Location: <remote/hybrid/onsite + city + radius>.
Work type: <full-time/contract/part-time>.
Industry: <domains>.
Salary min: <amount + currency>.
Max age days: <N>.
Exclude: <terms>.
"""

@app.on_event("startup")
def on_startup():
    print("=== AI Job Agent Server started ===")
    print("Use POST /intent or POST /run from Swagger UI at /docs")
    print("\n-- Intent Interview Questions --")
    for q in INTENT_QUESTIONS:
        print(q)
    print("\n-- Copy/Paste Template --")
    print(INTENT_TEMPLATE)

@app.get("/prompt")
def intent_prompt():
    return {
        "questions": INTENT_QUESTIONS,
        "template": INTENT_TEMPLATE
    }

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

