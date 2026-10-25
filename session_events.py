"""Inspect Codex session JSONL for documented, explicit terminal turn events."""
import json
from pathlib import Path

def collect(root, positions):
    events = []
    updated = dict(positions)
    for path in sorted(Path(root).glob("*/*/*/*.jsonl")):
        key = str(path)
        size = path.stat().st_size
        if key not in positions:
            updated[key] = 0
        offset = updated[key]
        if offset > size:
            updated[key] = size
            continue
        project = "Codex"
        try:
            with path.open("rb") as meta_stream:
                meta = json.loads(meta_stream.readline())
                if meta.get("type") == "session_meta":
                    project = Path(meta.get("payload", {}).get("cwd") or "Codex").name
        except (OSError, ValueError):
            pass
        with path.open("rb") as handle:
            handle.seek(updated[key])
            while True:
                raw = handle.readline()
                if not raw or not raw.endswith(b"\n"):
                    break
                updated[key] = handle.tell()
                try:
                    record = json.loads(raw)
                except ValueError:
                    continue
                if record.get("type") == "session_meta":
                    project = Path(record.get("payload", {}).get("cwd") or "Codex").name
                if record.get("type") != "event_msg":
                    continue
                payload = record.get("payload", {})
                kind = payload.get("type")
                if kind == "task_complete":
                    events.append({"event": "finished", "outcome": "completed", "project": project, "session": path.stem})
                elif kind in ("turn_aborted", "task_failed"):
                    events.append({"event": "finished", "outcome": "failed", "project": project, "session": path.stem})
    return updated, events
