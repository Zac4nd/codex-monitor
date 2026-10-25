"""Classify explicit Codex turn outcomes; never infer success from process exit alone."""
import json

def classify_event(record):
    if record.get("type") == "turn.completed":
        return "completed"
    if record.get("type") in ("turn.failed", "error"):
        return "failed"
    if record.get("event") == "finished":
        return "unknown"
    return None

def classify_jsonl(lines):
    """Return outcome for last known terminal turn event from codex exec --json."""
    terminal = None
    for line in lines:
        try:
            item = json.loads(line)
        except (ValueError, TypeError):
            continue
        result = classify_event(item)
        if result in ("completed", "failed"):
            terminal = result
    return terminal or "unknown"

def reconcile_finished(event, structured_events=()):
    """Outcome only if the caller explicitly associates logs with this execution."""
    if event.get("event") != "finished":
        raise ValueError("Expected finished event")
    return {**event, "outcome": classify_jsonl(structured_events)}
