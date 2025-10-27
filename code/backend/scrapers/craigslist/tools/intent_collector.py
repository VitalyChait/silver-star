# tools/intent_collector.py

from __future__ import annotations
import json, os, re, logging
from typing import Any, Dict, List, Optional

# ---- CrewAI BaseTool compat ----
try:
    from crewai.tools import BaseTool as _CrewBaseTool
except Exception:
    try:
        from crewai_tools import BaseTool as _CrewBaseTool
    except Exception:
        class _CrewBaseTool:
            name: str = "BaseTool"
            description: str = ""
            def __init__(self, **kwargs):
                for k, v in kwargs.items():
                    setattr(self, k, v)
            def run(self, **kwargs):
                raise NotImplementedError

# ---- LLM client ----
from openai import OpenAI

# ---- Pydantic schema ----
from pydantic import BaseModel, Field, ValidationError

class Location(BaseModel):
    type: Optional[str] = Field(default=None)  # remote|hybrid|onsite
    city: Optional[str] = None
    radius_km: Optional[int] = None

class Intent(BaseModel):
    keywords: List[str] = []
    must_have: List[str] = []
    nice_to_have: List[str] = []
    job_categories: List[str] = []
    location: Optional[Location] = None
    work_type: List[str] = []
    seniority: List[str] = []
    salary_min: Optional[str] = None
    max_age_days: int = 14
    exclude_terms: List[str] = []
    availability_hours_per_week: Optional[int] = None
    notes: Optional[str] = None

DEBUG = os.getenv("DEBUG_INTENT", "0") == "1"
log = logging.getLogger("intent")
if DEBUG:
    logging.basicConfig(level=logging.INFO)

SYSTEM_PROMPT = """You are a structured intent extraction agent for a job search AI.
Given a freeform description of what the user is looking for,
extract a JSON object with fields describing their search.

Return JSON only, no commentary.
Fields:
- keywords: core words/phrases describing the role.
- must_have: specific skills/technologies (if any).
- nice_to_have: secondary skills.
- job_categories: a list of broad categories from this taxonomy:
  ["software engineering","data science & ml","product management","design & ux",
   "it & support","sales & business dev","marketing & content","finance & accounting",
   "operations & hr","customer success","education & tutoring","healthcare",
   "construction & trades","logistics & warehouse","hospitality & retail",
   "writing & editing","legal","real estate","manufacturing","admin & office",
   "engineering","science & biotech"]
- location: object {type, city, region, country} if mentioned.
- work_type: ["full_time","part_time","contract"] if relevant.
- seniority: ["junior","mid","senior","lead","principal"] if relevant.
- salary_min: number if mentioned.
- max_age_days: how fresh the posting should be.
- exclude_terms: keywords to exclude.
- notes: any additional context.

Example 1:
User: "I'm a retired nurse looking for work."
→
{
  "keywords": ["nurse","healthcare","retired"],
  "must_have": [],
  "nice_to_have": [],
  "job_categories": ["healthcare"],
  "location": {"type": "unspecified"},
  "work_type": ["part_time"],
  "seniority": [],
  "salary_min": null,
  "max_age_days": 30,
  "exclude_terms": [],
  "notes": "retired nurse looking for part-time healthcare work"
}

Example 2:
User: "I'm an English teacher looking to tutor kids online."
→
{
  "keywords": ["english","tutor","teacher","kids","online"],
  "job_categories": ["education & tutoring"],
  "work_type": ["part_time"],
  "location": {"type": "remote"},

Inference rules:
- If user implies tutoring/teaching (e.g., “tutor”, “teacher”), include "education & tutoring" in job_categories.
- If user says “few hours/week” or similar, set work_type to ["part_time"] and set availability_hours_per_week if a number is present.
- Detect remote/hybrid/onsite from "remote", "online", "virtual", "zoom", "onsite", "in person", "hybrid".
- Parse salary if present; choose '/hr' for small numbers (<200) else '/yr'.
- Prefer concise arrays and avoid duplicates.
- If uncertain, leave fields null/empty.
Return JSON only.
"""

EXAMPLES = [
    {
        "user": "I'm a retired English teacher looking to tutor kids a few hours a week, ideally online.",
        "assistant": {
            "keywords": ["english", "tutor", "kids"],
            "must_have": [],
            "nice_to_have": ["online", "after-school"],
            "job_categories": ["education & tutoring"],
            "location": {"type": "remote", "city": None, "radius_km": None},
            "work_type": ["part_time"],
            "seniority": [],
            "salary_min": None,
            "max_age_days": 14,
            "exclude_terms": ["unpaid", "internship"],
            "availability_hours_per_week": 5,
            "notes": "Retired teacher; prefers online tutoring a few hours weekly."
        }
    }
]

def build_messages(user_text: str) -> list[dict[str, str]]:
    msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
    for ex in EXAMPLES:
        msgs.append({"role": "user", "content": ex["user"]})
        msgs.append({"role": "assistant", "content": json.dumps(ex["assistant"], ensure_ascii=False)})
    msgs.append({"role": "user", "content": user_text})
    return msgs

_JSON_RE = re.compile(r"\{.*\}\s*$", re.S)
def extract_json_maybe(s: str) -> str:
    m = _JSON_RE.search(s.strip())
    return m.group(0) if m else s.strip()

# --------- tiny fallback heuristics (kick in when LLM returns empty-ish) -----

HOURS_RE = re.compile(r"(\d{1,3})\s*(?:\+?\s*)?(?:hours?|hrs?)\b", re.I)
SAL_RE = re.compile(r"(?P<cur>usd|\$|eur|€|gbp|£)?\s*(?P<num>\d{2,3}(?:[,]\d{3})*|\d{4,6})(?:\s*-\s*(?P<num2>\d{2,3}(?:[,]\d{3})*|\d{4,6}))?\s*(?:per\s*(year|yr|hr|hour|month|mo))?", re.I)

def norm(s: str) -> str:
    return " ".join((s or "").lower().split())

def infer_simple(text: str) -> Dict[str, Any]:
    """Minimal, fast, and safe extractions for tutoring prompts."""
    t = norm(text)
    out: Dict[str, Any] = {}

    # categories
    if any(w in t for w in ["tutor", "tutoring", "teacher", "teaching"]):
        out.setdefault("job_categories", []).append("education & tutoring")

    # work_type and hours
    if any(p in t for p in ["few hours", "couple hours", "hours a week", "part time", "part-time", "pt"]):
        out["work_type"] = ["part_time"]
    m = HOURS_RE.search(text)
    if m:
        out["availability_hours_per_week"] = int(m.group(1))
        out.setdefault("work_type", ["part_time"])

    # location kind
    if any(w in t for w in ["remote", "online", "virtual", "zoom"]):
        out["location"] = {"type": "remote", "city": None, "radius_km": None}
    elif "hybrid" in t:
        out["location"] = {"type": "hybrid", "city": None, "radius_km": None}
    elif any(w in t for w in ["onsite", "on-site", "in person", "in-person"]):
        out["location"] = {"type": "onsite", "city": None, "radius_km": None}

    # salary
    sm = SAL_RE.search(text)
    if sm:
        cur = (sm.group("cur") or "USD").upper().replace("$","USD").replace("€","EUR").replace("£","GBP")
        lo = int(sm.group("num").replace(",", ""))
        unit = "hour" if lo < 200 else "yr"
        out["salary_min"] = f"{cur} {lo}/{unit}"

    # default excludes for tutoring
    out.setdefault("exclude_terms", [])
    for term in ["unpaid", "internship"]:
        if term not in out["exclude_terms"]:
            out["exclude_terms"].append(term)

    return out

def merge_intents(primary: Dict[str, Any], fallback: Dict[str, Any]) -> Dict[str, Any]:
    """Only fill empty slots from fallback; don’t override non-empty LLM fields."""
    merged = dict(primary)
    for k, v in fallback.items():
        if k not in merged or merged[k] in (None, "", [], {}):
            merged[k] = v
    # make arrays unique/sorted
    for arr_key in ["keywords","must_have","nice_to_have","job_categories","work_type","seniority","exclude_terms"]:
        if arr_key in merged and isinstance(merged[arr_key], list):
            merged[arr_key] = sorted({*merged[arr_key]})
    return merged

def is_too_empty(intent: Intent) -> bool:
    return (
        not intent.job_categories and
        not intent.work_type and
        intent.location is None and
        intent.salary_min is None and
        intent.availability_hours_per_week is None
    )

# ... keep all your imports, helpers, schemas, etc. above ...

class IntentCollectorTool(_CrewBaseTool):
    name: str = "IntentCollectorTool"
    description: str = "LLM-first parser that turns free text into structured job intent JSON with safe fallbacks."

    # CrewAI (newer) calls `_run`; some older code calls `run`.
    # We implement both and delegate to a single implementation.

    def _run(self, user_responses: str) -> str:  # CrewAI abstract method
        return self._run_impl(user_responses)

    def run(self, user_responses: str) -> str:   # Backward-compat
        return self._run_impl(user_responses)

    def _run_impl(self, user_responses: str) -> str:
        user_text = user_responses or ""
        model_name = os.getenv("LLM_MODEL", "gpt-4o-mini")
        api_key = os.getenv("OPENAI_API_KEY")

        # 1) Try LLM, but fall back safely on *any* error and ALWAYS return JSON
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            msgs = build_messages(user_text)
            resp = client.chat.completions.create(
                model=model_name,
                messages=msgs,
                temperature=0,
                response_format={"type": "json_object"},
            )
            content = resp.choices[0].message.content
            data = json.loads(extract_json_maybe(content))
        except Exception:
            data = {}

        # 2) Validate; if “too empty”, apply heuristics
        try:
            intent = Intent.model_validate(data)
        except Exception:
            intent = Intent()

        if is_too_empty(intent):
            heuristic = infer_simple(user_text)
            merged = merge_intents(intent.model_dump(), heuristic)
            intent = Intent(**merged)

        # 3) Final JSON string (never empty / never non-JSON)
        return intent.model_dump_json(exclude_none=True, ensure_ascii=False)
