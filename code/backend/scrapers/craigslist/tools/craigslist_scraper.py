# tools/craigslist_scraper.py
from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode

from scrapingbee import ScrapingBeeClient
from bs4 import BeautifulSoup

import time
import random
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Referer": "https://www.google.com/",
}

def _with_rss(url: str) -> str:
    """Append format=rss to the CL search URL (keeps existing params)."""
    parts = urlsplit(url)
    q = dict(parse_qsl(parts.query))
    q["format"] = "rss"
    newq = urlencode(q)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, newq, parts.fragment))
    
# =============================================================================
# Configuration
# =============================================================================

# Broad bucket -> Craigslist JOB subcategory
CL_CATEGORY_CODE: Dict[str, str] = {
    "software engineering": "sof",
    "data science & ml":    "sci",
    "product management":   "bus",
    "design & ux":          "med",
    "it & support":         "sof",
    "sales & business dev": "sal",
    "marketing & content":  "mkt",
    "finance & accounting": "acc",
    "operations & hr":      "bus",
    "customer success":     "cus",
    "education & tutoring": "edu",
    "healthcare":           "hea",
    "construction & trades":"trd",
    "logistics & warehouse":"trp",
    "hospitality & retail": "fbh",
    "writing & editing":    "med",
    "legal":                "lgl",
    "real estate":          "rea",
    "manufacturing":        "mnu",
    "admin & office":       "ofc",
    "engineering":          "eng",
    "science & biotech":    "sci",
}

# SERVICES section categories (subset most relevant to knowledge/gig work)
CL_SERVICE_CODE: Dict[str, str] = {
    "computer services": "cps",
    "creative services": "crs",
    "lessons & tutoring": "lss",
    "all services": "bbb",  # catch-all
}

# For each broad bucket, which SERVICES buckets make sense as fallbacks
BUCKET_TO_SERVICE_CODES: Dict[str, List[str]] = {
    "software engineering": ["cps"],
    "data science & ml":    ["cps"],
    "product management":   ["crs"],
    "design & ux":          ["crs"],
    "it & support":         ["cps"],
    "sales & business dev": ["crs"],
    "marketing & content":  ["crs"],
    "finance & accounting": ["crs"],
    "operations & hr":      ["crs"],
    "customer success":     ["crs"],
    "education & tutoring": ["lss"],
    "healthcare":           [],      # usually jobs-only; still gets global fallbacks
    "construction & trades":["crs"],
    "logistics & warehouse":[],
    "hospitality & retail": [],
    "writing & editing":    ["crs"],
    "legal":                ["crs"],
    "real estate":          ["crs"],
    "manufacturing":        [],
    "admin & office":       ["crs"],
    "engineering":          ["cps"],
    "science & biotech":    ["cps"],
}

# Low-priority global sweep (jobs) to try if nothing else hits
ALL_JOB_CODES: List[str] = [
    "sof","eng","sci","edu","hea","acc","ofc","bus","mkt","sal","ret",
    "fbh","cus","trd","med","lgl","rea","trp","mnu","jjj"  # jjj = all jobs
]

# Craigslist employment type mapping (jobs only)
# 1 = full-time, 2 = part-time, 3 = contract, 4 = employee's choice
EMPLOYMENT_TYPE_MAP: Dict[str, int] = {
    "full_time": 1,
    "part_time": 2,
    "contract":  3,
}

# Sites we "know" by slug (used by the simple city->site resolver)
COMMON_SITES = {
    "boston","newyork","sfbay","chicago","losangeles","seattle","austin",
    "atlanta","miami","dallas","denver","sandiego","portland"
}

# =============================================================================
# Helpers
# =============================================================================

def _norm(s: Any) -> str:
    return " ".join(str(s or "").lower().split())

def _get_client() -> ScrapingBeeClient:
    key = os.getenv("SCRAPINGBEE_API_KEY")
    if not key:
        raise RuntimeError("Missing SCRAPINGBEE_API_KEY (or API_KEY).")
    return ScrapingBeeClient(api_key=key)

def _site_from_intent(intent: Dict[str, Any], default_site: Optional[str] = None) -> str:
    """
    Resolve a Craigslist site subdomain from intent.location.city (best-effort).
    Defaults to env CL_SITE_DEFAULT.
    """
    default_site = default_site or os.getenv("CL_SITE_DEFAULT")
    loc = intent.get("location") or {}
    city = (loc.get("city") if isinstance(loc, dict) else loc) or ""
    if isinstance(city, str) and city.strip():
        slug = re.sub(r"[^a-z]", "", city.strip().lower())
        if slug in COMMON_SITES:
            return slug
    return default_site

def _sites_for_intent(intent: Dict[str, Any]) -> List[str]:
    """
    If location.type == 'remote', optionally fan out across multiple metros.
    REMOTE_SITES env var: comma-separated list, e.g. 'boston,sfbay,newyork'
    Otherwise, use a single site (city->site or default).
    """
    remote = False
    loc = intent.get("location")
    if isinstance(loc, dict):
        remote = (loc.get("type") == "remote")
    elif isinstance(loc, str):
        remote = (loc.strip().lower() == "remote")

    if remote:
        env = os.getenv("REMOTE_SITES")
        if env:
            sites = [s.strip() for s in env.split(",") if s.strip()]
            return sites[:8]  # cap to be safe
    return [_site_from_intent(intent)]

def _employment_type_param(intent: Dict[str, Any]) -> Optional[int]:
    """
    Map work_type (list or string) to Craigslist employment_type (jobs only).
    Preference: part_time > contract > full_time for gig-like roles.
    """
    wt = intent.get("work_type")
    if isinstance(wt, list) and wt:
        for t in ["part_time", "contract", "full_time"]:
            if t in wt:
                return EMPLOYMENT_TYPE_MAP.get(t)
        return EMPLOYMENT_TYPE_MAP.get(wt[0])
    if isinstance(wt, str) and wt:
        return EMPLOYMENT_TYPE_MAP.get(wt)
    return None

def _query_from_intent(intent: Dict[str, Any]) -> str:
    """
    Build a short, high-precision query string.
    - Prefer key head terms per bucket (e.g., healthcare -> 'nurse').
    - Strip generic words ('retired', 'looking', 'work').
    - Dedup and keep <= 3 tokens.
    """
    # Pull raw tokens
    kw = (intent.get("keywords") or []) + (intent.get("must_have") or [])
    notes = intent.get("notes") or ""
    raw_tokens = [t for t in re.split(r"\W+", " ".join(kw) + " " + notes) if t]

    STOP = {
        "retired","looking","for","work","job","jobs","hire","hiring",
        "a","an","the","and","or","to","with","in","of","on","my","me","please",
        "remote","onsite","hybrid"
    }
    tokens = [t.lower() for t in raw_tokens if t and t.lower() not in STOP]

    # Heuristic head terms by bucket
    buckets = [b.lower() for b in (intent.get("job_categories") or [])]
    text = " ".join(tokens)

    # Healthcare
    if ("healthcare" in buckets) or any(w in text for w in ["nurse","nursing","rn","lpn","cna"]):
        # Prefer a single strong term
        return "nurse"

    # Education & Tutoring
    if ("education & tutoring" in buckets) or any(w in text for w in ["tutor","teacher","teaching","lesson","esl","ela"]):
        # Try to preserve a subject if present (e.g., math/english)
        subject = None
        for s in ["math","english","reading","science","esl","spanish","chemistry","physics","writing"]:
            if s in tokens:
                subject = s; break
        return f"{subject} tutor" if subject else "tutor"

    # Software / IT
    if ("software engineering" in buckets) or any(w in text for w in ["software","developer","engineer","programmer","ios","android","backend","frontend","fullstack","full-stack"]):
        return "software developer"

    # Data / ML
    if ("data science & ml" in buckets) or any(w in text for w in ["ml","ai","machine","learning","data","scientist","analytics"]):
        return "data scientist"

    # Writing / Editing
    if ("writing & editing" in buckets) or any(w in text for w in ["writer","copywriter","editing","editor","proofread","content"]):
        return "writer"

    # Marketing
    if ("marketing & content" in buckets) or any(w in text for w in ["marketing","seo","sem","social","growth"]):
        return "marketing"

    # Sales
    if ("sales & business dev" in buckets) or any(w in text for w in ["sales","bd","business","development"]):
        return "sales"

    # Fallback: keep up to 2 non-stop tokens
    dedup = []
    for t in tokens:
        if t not in dedup:
            dedup.append(t)
        if len(dedup) >= 2:
            break
    return " ".join(dedup)


# =============================================================================
# Category candidate generation (jobs + services + global fallbacks)
# =============================================================================

def pick_craigslist_candidates(intent: Dict[str, Any]) -> List[Tuple[str, str]]:
    """
    Ordered (section, code):
      • Relevant JOB subcats inferred from intent
      • Related SERVICES subcats
      • Broad catch-alls: jjj (jobs), ggg (gigs), bbb (services)
    """
    seen: set[Tuple[str, str]] = set()
    out: List[Tuple[str, str]] = []

    def add(section: str, code: str):
        key = (section, code)
        if code and key not in seen:
            seen.add(key); out.append(key)

    # Explicit bucket(s)
    for cat in (intent.get("job_categories") or []):
        code = CL_CATEGORY_CODE.get(cat.lower())
        if code:
            add("jobs", code)
            for svc in BUCKET_TO_SERVICE_CODES.get(cat.lower(), []):
                add("services", svc)

    text = _norm(" ".join(intent.get("keywords") or []) + " " + (intent.get("notes") or ""))

    # Healthcare
    if any(w in text for w in ["doctor","nurse","nursing","rn","lpn","cna"]):
        add("jobs", "hea")

    # Tutoring / Teaching
    if any(w in text for w in ["tutor","teacher","teaching","esl","ela","lesson"]):
        add("jobs", "edu"); add("services", "lss")

    # Software / IT
    if any(w in text for w in ["software","developer","engineer","programmer","ios","android","backend","frontend","fullstack","full-stack","it support","helpdesk","sysadmin"]):
        add("jobs", "sof"); add("services", "cps")

    # Data / ML (only when ML/data indicated)
    if any(w in text for w in ["data scientist","data science","machine learning","ml","ai","analytics"]):
        add("jobs", "sci"); add("services", "cps")

    # Writing / Editing
    if any(w in text for w in ["writer","copywriter","editing","editor","proofread","content"]):
        add("jobs", "med"); add("services", "crs")

    # Marketing
    if any(w in text for w in ["marketing","seo","sem","social media","growth"]):
        add("jobs", "mkt"); add("services", "crs")

    # Sales (only if actually mentioned)
    if any(w in text for w in ["sales","bd","business development"]):
        add("jobs", "sal"); add("services", "crs")

    # Admin / Office
    if any(w in text for w in ["admin","office","assistant","reception"]):
        add("jobs", "ofc"); add("services", "crs")

    # Catch-alls
    add("jobs", "jjj")
    add("gigs", "ggg")
    add("services", "bbb")

    return out


# =============================================================================
# URL building (multi-URL across categories and sites)
# =============================================================================


def build_craigslist_urls(intent: Dict[str, Any], max_urls: int = 12) -> List[str]:
    """
    Build a capped list of Craigslist URLs across:
      • inferred JOB subcats,
      • related SERVICES subcats,
      • and broad catch-alls for JOBS/JIGS/SERVICES.
    employment_type is appended only for JOBS.
    """
    sites = _sites_for_intent(intent)
    candidates = pick_craigslist_candidates(intent)
    query = _query_from_intent(intent)
    emp = _employment_type_param(intent)  # jobs only

    urls: List[str] = []
    for site in sites:
        for section, code in candidates:
            params: Dict[str, str] = {}
            if query:
                params["query"] = query
            if section == "jobs" and emp:
                params["employment_type"] = str(emp)
            qs = f"?{urlencode(params)}" if params else ""
            urls.append(f"https://{site}.craigslist.org/search/{code}{qs}")
            if len(urls) >= max_urls:
                return urls
    return urls

# =============================================================================
# Fetch + parse
# =============================================================================

def _text(el) -> str:
    return (el.get_text(strip=True) if el else "").strip()

def parse_craigslist_results(html: bytes | str, base_url: str) -> List[Dict[str, Any]]:
    """
    Parse a Craigslist search results page (jobs or services).
    Tries several selector variants to survive layout changes.
    Returns a list of dicts with: title, apply_url, posted_at, location, company?, snippet, etc.
    """
    soup = BeautifulSoup(html, "html.parser")
    results: List[Dict[str, Any]] = []

    # Try several container selectors (old/new layouts)
    containers = (
        soup.select("li.cl-search-result") or
        soup.select("div.cl-search-result") or
        soup.select("li.result-row") or
        soup.select(".cl-static-search-result")
    )

    for el in containers:
        # link & title
        a = el.select_one("a.posting-title") or el.select_one("a.result-title") or el.find("a")
        href = a["href"] if (a and a.has_attr("href")) else ""
        title = (
            _text(a.select_one(".label")) or
            _text(a.select_one(".title")) or
            (a.get("title") or "").strip() if a and a.get("title") else "" or
            _text(a)
        )

        # meta: location/company (best-effort)
        hood = _text(el.select_one(".result-hood"))
        loc = hood.strip("() ") if hood else ""
        company = _text(el.select_one(".company")) or ""

        # date
        time_tag = el.find("time") or el.select_one("time.result-date")
        posted_at = time_tag.get("datetime") if (time_tag and time_tag.has_attr("datetime")) else _text(time_tag)

        # snippet
        snippet = _text(el.select_one(".snippet")) or _text(el.select_one(".result-snippet"))

        if title or href:
            results.append({
                "title": title or "Untitled",
                "company": company or None,
                "location": loc or None,
                "snippet": snippet or None,
                "apply_url": href,
                "posted_at": posted_at or None,
                "source": "craigslist",
                "source_url": base_url,
                "badges": [],
            })

    return results

def fetch_craigslist(intent: Dict[str, Any], max_results: int = 60) -> Tuple[List[Dict[str, Any]], List[str], List[str], List[Dict[str, str]]]:
    """
    Multi-URL CL search with ScrapingBee + resilient fallbacks:
      • Primary: HTML with browser headers
      • Retry: tweak params (render_js flip)
      • Fallback: RSS (&format=rss) parse
    Returns: (jobs, attempted_urls, hit_urls, errors)
    """
    urls = build_craigslist_urls(intent)
    client = _get_client()

    # Keep a stable session so cookies can persist across requests
    session_id = os.getenv("SCRAPINGBEE_SESSION_ID")

    jobs: List[Dict[str, Any]] = []
    attempted: List[str] = []
    hits: List[str] = []
    errors: List[Dict[str, str]] = []

    def _sleep_jitter():
        time.sleep(0.4 + random.random() * 0.4)

    def try_html(url: str, render_js: bool) -> Tuple[bool, List[Dict[str, Any]], Optional[str]]:
        SAFE_PARAMS_BASE = {
            # Craigslist search is server-side, start with no JS
            "render_js": "false",
            "block_resources": "true",
            "country_code": "US",
            "premium_proxy": "true",
            # Helps blend in without extra knobs that cause 400
            "stealth_proxy": "true",
            # small wait to avoid occasional blank responses
            "wait": "800"
        }
        try:
            resp = client.get(url, params=dict(SAFE_PARAMS_BASE), headers=BROWSER_HEADERS)
            if resp.status_code != 200:
                return False, [], f"http {resp.status_code}"
            chunk = parse_craigslist_results(resp.content, base_url=url)
            return (len(chunk) > 0), chunk, None
        except Exception as e:
            return False, [], repr(e)

    def try_rss(url: str) -> Tuple[bool, List[Dict[str, Any]], Optional[str]]:
        rss_url = _with_rss(url)
        try:
            # RSS doesn’t need heavy params; still keep session & headers
            SAFE_PARAMS_BASE = {
                # Craigslist search is server-side, start with no JS
                "render_js": "false",
                "block_resources": "true",
                "country_code": "US",
                "premium_proxy": "true",
                # Helps blend in without extra knobs that cause 400
                "stealth_proxy": "true",
                # small wait to avoid occasional blank responses
                "wait": "800"
            }
            resp = client.get(rss_url, params=dict(SAFE_PARAMS_BASE), headers=BROWSER_HEADERS)
            if resp.status_code != 200:
                return False, [], f"http {resp.status_code}"
            # Parse RSS with BeautifulSoup (xml)
            soup = BeautifulSoup(resp.content, "xml")
            items = soup.find_all("item")
            parsed: List[Dict[str, Any]] = []
            for it in items:
                title = (it.title.text or "").strip() if it.title else ""
                link = (it.link.text or "").strip() if it.link else ""
                date = (it.pubDate.text or "").strip() if it.pubDate else ""
                desc = (it.description.text or "").strip() if it.description else ""
                if title or link:
                    parsed.append({
                        "title": title or "Untitled",
                        "company": None,
                        "location": None,  # RSS rarely includes hood; leave None
                        "snippet": desc or None,
                        "apply_url": link,
                        "posted_at": date or None,
                        "source": "craigslist",
                        "source_url": rss_url,
                        "badges": [],
                    })
            return (len(parsed) > 0), parsed, None
        except Exception as e:
            return False, [], repr(e)

    for url in urls:
        attempted.append(url)

        # 1) HTML, no JS (fast)
        ok, chunk, err = try_html(url, render_js=False)
        if ok:
            hits.append(url); jobs.extend(chunk)
            if len(jobs) >= max_results: break
            _sleep_jitter(); continue
        if err and err.startswith("http "):
            # 2) HTML, flip render_js for a different fingerprint
            ok2, chunk2, err2 = try_html(url, render_js=True)
            if ok2:
                hits.append(url); jobs.extend(chunk2)
                if len(jobs) >= max_results: break
                _sleep_jitter(); continue
            # 3) RSS fallback as last resort for this URL
            ok3, chunk3, err3 = try_rss(url)
            if ok3:
                hits.append(_with_rss(url)); jobs.extend(chunk3)
                if len(jobs) >= max_results: break
                _sleep_jitter(); continue
            # Record the last error we saw in this chain
            errors.append({"url": url, "error": err3 or err2 or err})
        else:
            # non-HTTP error (exception) or HTML parsed 0 items, try RSS anyway
            ok3, chunk3, err3 = try_rss(url)
            if ok3:
                hits.append(_with_rss(url)); jobs.extend(chunk3)
                if len(jobs) >= max_results: break
                _sleep_jitter(); continue
            errors.append({"url": url, "error": err3 or (err or "no results")})

        _sleep_jitter()

    # De-dup by (title, apply_url)
    dedup: Dict[Tuple[Optional[str], Optional[str]], Dict[str, Any]] = {}
    for j in jobs:
        key = (j.get("title"), j.get("apply_url"))
        dedup[key] = j
    merged = list(dedup.values())

    return merged[:max_results], attempted, hits, errors
