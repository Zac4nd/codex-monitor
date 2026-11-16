"""Read Codex session JSONL incrementally; preserve turn/activity association."""
import json
from pathlib import Path
from activity_metadata import activity_for_session, clean_label, extract_activity, _user_text

def collect(root, positions, labels=None):
    events = []
    updated = dict(positions)
    labels = labels or {}
    for path in sorted(Path(root).glob("*/*/*/*.jsonl")):
        key = str(path)
        try:
            size = path.stat().st_size
        except OSError:
            continue
        offset = positions.get(key, 0)
        if offset > size:
            updated[key] = size
            continue
        updated[key] = offset
        project = "Codex"
        try:
            with path.open("rb") as meta_stream:
                meta = json.loads(meta_stream.readline())
                if meta.get("type") == "session_meta":
                    project = Path(meta.get("payload", {}).get("cwd") or "Codex").name
        except (OSError, ValueError):
            pass
        explicit = clean_label(labels.get(key))
        # For an already-open turn, recover only history *before* this cursor.
        current_activity = activity_for_session(path, upto=offset) if offset else None
        turn_events = []
        pending_start = None
        prestart_activity = None
        in_turn = bool(offset)
        try:
            with path.open("rb") as stream:
                stream.seek(offset)
                while True:
                    raw = stream.readline()
                    if not raw or not raw.endswith(b"\n"):
                        break
                    updated[key] = stream.tell()
                    try:
                        record = json.loads(raw)
                    except ValueError:
                        continue
                    if record.get("type") == "session_meta":
                        project = Path(record.get("payload", {}).get("cwd") or "Codex").name
                    user_texts = _user_text(record)
                    for user_text in user_texts:
                        if user_text.startswith(("# AGENTS.md instructions", "<environment_context>")):
                            continue
                        extracted = extract_activity(user_text)
                        prestart_activity = extracted
                        if in_turn:
                            current_activity = extracted
                            if pending_start is not None and current_activity:
                                pending_start["activity"] = current_activity
                    if record.get("type") != "event_msg":
                        continue
                    kind = (record.get("payload") or {}).get("type")
                    if kind == "task_started":
                        current_activity = prestart_activity
                        prestart_activity = None
                        in_turn = True
                        pending_start = {"event": "started", "project": project, "session": path.stem,
                                         "session_file": key, "start_offset": stream.tell()}
                        if current_activity:
                            pending_start["activity"] = current_activity
                        turn_events.append(pending_start)
                    elif kind in ("task_complete", "turn_aborted", "task_failed"):
                        event = {"event": "finished", "project": project, "session": path.stem,
                                 "outcome": "completed" if kind == "task_complete" else "failed"}
                        if current_activity:
                            event["activity"] = current_activity
                        turn_events.append(event)
                        pending_start = None
                        in_turn = False
                        prestart_activity = None
        except OSError:
            continue
        for event in turn_events:
            if explicit:
                event["activity"] = explicit
            events.append(event)
    return updated, events
