"""Send notifications from structured Codex session events; no PID inference."""
import json
from pathlib import Path
from session_events import collect
from ntfy_notifier import publish
from ntfy_settings import read

def poll(root, state_file, sender=publish, config=None):
    config = read() if config is None else config
    if not config.get("enabled"):
        return 0
    state_file = Path(state_file)
    if not state_file.exists():
        # Baseline all existing sessions; don't replay history.
        offsets = {str(p): p.stat().st_size for p in Path(root).glob("*/*/*/*.jsonl")}
        state_file.write_text(json.dumps(offsets))
        return 0
    positions = json.loads(state_file.read_text())
    positions, events = collect(root, positions)
    # Commit offsets before delivering to guarantee at-most-once attempts.
    state_file.write_text(json.dumps(positions))
    count = 0
    for event in events:
        category = ("notify_start" if event.get("event") == "started" else
                    "notify_error" if event.get("outcome") == "failed" else "notify_complete")
        if not config.get(category, True):
            continue
        try:
            result = sender(event, config)
            count += bool(result.get("sent"))
        except Exception as exc:
            import logging
            logging.warning("Session alert failed: %s", exc)
    return count
