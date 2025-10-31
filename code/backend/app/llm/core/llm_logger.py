import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict


def _enabled() -> bool:
    val = os.getenv("LLM_LOGS_ENABLED", "1")
    return str(val).lower() not in {"0", "false", "no"}


def _repo_root() -> Path:
    """Locate the repo root preferring a directory that contains .git.

    If .git isn't found, use the highest ancestor containing a README.md.
    Fallback to CWD.
    """
    here = Path(__file__).resolve()
    parents = [here.parent] + list(here.parents)
    # Prefer the first directory up the chain that has a .git folder
    for parent in parents:
        if (parent / ".git").exists():
            return parent
    # Otherwise choose the topmost README.md holder
    readme_holder: Path | None = None
    for parent in parents:
        if (parent / "README.md").exists():
            readme_holder = parent
    if readme_holder is not None:
        return readme_holder
    return Path.cwd()


def _log_dir() -> Path:
    # Always place logs under repo_root/logs/llm
    return _repo_root() / "logs" / "llm"


def ensure_log_dir() -> None:
    if not _enabled():
        return
    d = _log_dir()
    d.mkdir(parents=True, exist_ok=True)


def log_event(role: str, event: Dict[str, Any]) -> None:
    """Append a single JSON line with timestamp to the per-role log file.

    Each line format: {"ts": ISO8601, "role": role, ...event}
    """
    if not _enabled():
        return

    ensure_log_dir()
    payload = {"ts": datetime.utcnow().isoformat() + "Z", "role": role or "unknown"}
    payload.update(event)

    # Use compact separators to keep a single line per event
    line = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    log_path = _log_dir() / f"{(role or 'unknown').replace('/', '_')}.log"
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        # Avoid raising from logging; silently ignore I/O errors
        pass
