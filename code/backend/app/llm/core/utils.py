import json
import re
from typing import Any, Dict, Iterable, List, Optional

ELLIPSIS = "..."


def clamp_text(value: Any, max_length: int = 180) -> Optional[str]:
    """Convert a value to a compact single-line string with length limits."""
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return str(value)

    if isinstance(value, (list, tuple, set)):
        return clamp_text(", ".join(str(item) for item in value), max_length)

    text = str(value)
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return None

    if len(text) > max_length:
        trimmed = text[: max_length - 1].rstrip()
        return f"{trimmed}{ELLIPSIS}"
    return text


def compact_json(
    data: Dict[str, Any],
    *,
    max_field_length: int = 200,
    max_total_chars: int = 1600
) -> str:
    """Serialize a dictionary to JSON with per-field and total length limits."""
    compacted: Dict[str, Any] = {}
    for key, value in data.items():
        compacted[key] = clamp_text(value, max_field_length)

    serialized = json.dumps(compacted, indent=2)
    if len(serialized) <= max_total_chars:
        return serialized

    trimmed = serialized[: max_total_chars - 1].rstrip()
    return f"{trimmed}{ELLIPSIS}"


def compact_jobs(
    jobs: Iterable[Dict[str, Any]],
    *,
    max_jobs: int = 25,
    max_field_length: int = 220,
    max_total_chars: int = 7000
) -> str:
    """Create a compact JSON representation of jobs for prompting."""
    trimmed_jobs: List[Dict[str, Any]] = []
    for job in jobs:
        if len(trimmed_jobs) >= max_jobs:
            break
        trimmed_jobs.append(
            {
                key: clamp_text(value, max_field_length)
                for key, value in job.items()
                if value is not None
            }
        )

    serialized = json.dumps(trimmed_jobs, indent=2)
    if len(serialized) <= max_total_chars:
        return serialized

    trimmed = serialized[: max_total_chars - 1].rstrip()
    return f"{trimmed}{ELLIPSIS}"


def strip_json_code_fences(text: str) -> str:
    """Remove common markdown code fences around JSON payloads."""
    if not text:
        return text

    stripped = text.strip()
    if stripped.startswith("```json"):
        stripped = stripped[7:]
    if stripped.startswith("```"):
        stripped = stripped[3:]
    if stripped.endswith("```"):
        stripped = stripped[:-3]
    return stripped.strip()


def extract_first_json_block(text: str) -> Optional[str]:
    """
    Extract the first valid JSON object/array substring from arbitrary text.

    Handles extra prose before/after and ignores braces inside JSON strings.
    Returns the JSON substring or None if not found.
    """
    if not text:
        return None
    s = text.strip()
    # Quick path: already pure JSON
    try:
        json.loads(s)
        return s
    except Exception:
        pass

    start_idx = -1
    opener = None
    for i, ch in enumerate(s):
        if ch in "[{":
            start_idx = i
            opener = ch
            break
    if start_idx == -1:
        return None
    closer = ']' if opener == '[' else '}'
    depth = 0
    in_str = False
    esc = False
    for j in range(start_idx, len(s)):
        c = s[j]
        if in_str:
            if esc:
                esc = False
            elif c == '\\':
                esc = True
            elif c == '"':
                in_str = False
            continue
        else:
            if c == '"':
                in_str = True
                continue
            if c == opener:
                depth += 1
            elif c == closer:
                depth -= 1
                if depth == 0:
                    candidate = s[start_idx:j+1]
                    try:
                        json.loads(candidate)
                        return candidate
                    except Exception:
                        return None
    return None
