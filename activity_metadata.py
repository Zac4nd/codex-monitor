"""Conservative, per-session activity labels. Never guess using project or timestamps."""
import json
import os
import re
from pathlib import Path

SESSION_ROOT = Path.home() / ".codex" / "sessions"
SPEC = re.compile(r"(?i)\bSPEC[-_ ]?(\d{2,4})\b")
HEADER = re.compile(r"(?i)^\s*(?:#{1,4}\s*)?(SPEC[-_ ]?\d{2,4})\s*[·:–-]\s*(.{2,65})$")
UNSAFE = re.compile(r"(?i)(https?://|[/\\]|@|\b(?:token|password|secret|apikey|api_key|bearer|credential|chiave|passwd)\b|[=<>]|[\x00-\x1f])")
ENV_LABEL = "CODEX_MONITOR_ACTIVITY"

def clean_label(label):
    """Allow short, human-readable titles only. Never send arbitrary prompts."""
    if not isinstance(label, str):
        return None
    label = " ".join(label.strip().split())
    if not 2 <= len(label) <= 65 or UNSAFE.search(label):
        return None
    if not re.fullmatch(r"[\wÀ-ÿ .·:()'–-]+", label, re.UNICODE):
        return None
    return label

def extract_activity(text):
    """Read only a clearly identified SPEC from a *single* user task."""
    if not isinstance(text, str) or len(text) > 100_000:
        return None
    # Only the first few lines of the task. Don't mine code/logs or AGENTS instructions.
    lines = [s.strip() for s in text[:1800].splitlines()[:12] if s.strip()]
    if not lines:
        return None
    for line in lines[:6]:
        match = HEADER.match(line)
        if match:
            spec = "SPEC-" + SPEC.search(match.group(1)).group(1)
            title = clean_label(match.group(2).strip(" .-–"))
            if title and not re.search(r"(?i)^(continuation|continued|proseguimento|ripresa)\b", title):
                return f"{spec} · {title[:42].rstrip()}"
            return spec
    # SPEC is safe even without a trustworthy description.
    head = " ".join(lines[:3])
    found = SPEC.findall(head)
    if found:
        return "SPEC-" + found[0]
    return None

def _user_text(record):
    if record.get("type") != "response_item":
        return []
    payload = record.get("payload") or {}
    if payload.get("type") != "message" or payload.get("role") != "user":
        return []
    return [entry.get("text", "") for entry in payload.get("content", [])
            if isinstance(entry, dict) and entry.get("type") in ("input_text", "text")]

def activity_for_session(path, upto=None):
    """Most recent unambiguous user task in this particular JSONL; bounded reads."""
    try:
        path = Path(path)
        size = path.stat().st_size
        if upto is not None:
            size = min(size, max(0, int(upto)))
        with path.open("rb") as stream:
            chunks = [stream.read(min(size, 262144))]
            if size > 262144:
                stream.seek(max(0, size - 393216))
                chunks.append(stream.read(393216))
    except OSError:
        return None
    label = None
    for chunk in chunks:
        # Skip a truncated first JSON line in a tail chunk.
        for raw in chunk.split(b"\n"):
            if not raw or len(raw) > 100000:
                continue
            try:
                record = json.loads(raw)
            except (ValueError, UnicodeError):
                continue
            for text in _user_text(record):
                if text.startswith(("# AGENTS.md instructions", "<environment_context>")):
                    continue
                result = extract_activity(text)
                # A new user task without a SPEC must not retain an older task's SPEC.
                label = result
    return label

def session_file_for_pid(pid, root=SESSION_ROOT, proc=Path("/proc")):
    """Exact open FD association. Multiple candidate sessions => no association."""
    try:
        base = (proc / str(int(pid)) / "fd")
        valid = []
        root = Path(root).resolve()
        for fd in base.iterdir():
            try:
                target = Path(os.readlink(fd)).resolve()
                if target.suffix == ".jsonl" and target.is_relative_to(root) and target.is_file():
                    valid.append(target)
            except (OSError, ValueError):
                continue
        unique = set(valid)
        return str(next(iter(unique))) if len(unique) == 1 else None
    except (OSError, ValueError):
        return None

def explicit_label(pid, proc=Path("/proc")):
    try:
        values = (proc / str(int(pid)) / "environ").read_bytes().split(b"\0")
        prefix = (ENV_LABEL + "=").encode()
        for value in values:
            if value.startswith(prefix):
                return clean_label(value[len(prefix):].decode("utf-8", "replace"))
    except (OSError, ValueError):
        pass
    return None

def resolve_process(pid):
    session = session_file_for_pid(pid)
    declared = explicit_label(pid)
    return {"session_file": session,
            "activity": declared or (activity_for_session(session) if session else None),
            "activity_source": "explicit" if declared else ("session" if session else None)}
