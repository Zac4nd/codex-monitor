"""Send notifications from structured Codex session events, waiting briefly for task metadata."""
import json
import logging
import os
import time
from pathlib import Path
from activity_metadata import _user_text, extract_activity
from session_events import collect
from ntfy_notifier import publish
from ntfy_settings import read

START_METADATA_TIMEOUT = 12.0

def _save_json(path, value):
    """Atomic state update: no partial cursor or pending-start files."""
    temp = path.with_name(path.name + f".{os.getpid()}.tmp")
    try:
        temp.write_text(json.dumps(value))
        os.chmod(temp, 0o600)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)

def _task_after_start(path, offset):
    """Find a real user task after one exact session/turn start, not a prior SPEC.

    Return (task_seen, activity). Don't treat injected AGENTS/environment as a task.
    """
    try:
        with Path(path).open("rb") as handle:
            handle.seek(offset)
            for _ in range(100):
                raw = handle.readline(110000)
                if not raw or not raw.endswith(b"\n"):
                    break
                try:
                    record = json.loads(raw)
                except (ValueError, UnicodeError):
                    continue
                if record.get("type") == "event_msg" and (record.get("payload") or {}).get("type") == "task_started":
                    break  # Never adopt a subsequent turn's task.
                for text in _user_text(record):
                    if text.startswith(("# AGENTS.md instructions", "<environment_context>")):
                        continue
                    return True, extract_activity(text)
    except (OSError, ValueError):
        pass
    return False, None

def poll(root, state_file, sender=publish, config=None, now=None):
    config = read() if config is None else config
    if not config.get("enabled"):
        return 0
    now = time.time() if now is None else now
    state_file = Path(state_file)
    if not state_file.exists():
        # Baseline existing sessions, do not replay historical starts.
        offsets = {str(p): p.stat().st_size for p in Path(root).glob("*/*/*/*.jsonl")}
        _save_json(state_file, offsets)
        return 0
    positions = json.loads(state_file.read_text())
    try:
        labels = json.loads((state_file.parent / "session-labels.json").read_text())
    except (OSError, ValueError):
        labels = {}
    pending_file = state_file.parent / "pending-start-notifications.json"
    try:
        pending = json.loads(pending_file.read_text())
        if not isinstance(pending, dict):
            pending = {}
    except (OSError, ValueError):
        pending = {}
    positions, events = collect(root, positions, labels)
    immediate = []
    for event in events:
        if event.get("event") != "started" or not config.get("notify_start", True):
            continue
        if event.get("session_file") and isinstance(event.get("start_offset"), int):
            key = event["session_file"] + ":" + str(event["start_offset"])
            if key in pending:
                continue
            if not event.get("activity"):
                pending[key] = {"event": event, "created": now}
                continue
        immediate.append(event)
    # Save pending before cursor so a crash cannot silently discard an unsent start.
    _save_json(pending_file, pending)
    _save_json(state_file, positions)

    # A task prompt often arrives 1-2s after task_started. Wait for it (or timeout)
    # without borrowing identifiers from earlier sessions/turns.
    for key, entry in list(pending.items()):
        if not config.get("notify_start", True):
            del pending[key]
            _save_json(pending_file, pending)
            continue
        event = entry["event"]
        seen, activity = _task_after_start(event["session_file"], event["start_offset"])
        if not seen and now - entry["created"] < START_METADATA_TIMEOUT:
            continue
        if activity:
            event["activity"] = activity
        immediate.append(event)
        del pending[key]
        # At-most-once delivery attempt, including after service restart.
        _save_json(pending_file, pending)

    sent = 0
    for event in immediate:
        try:
            result = sender(event, config)
            sent += int(bool(result.get("sent")))
        except Exception as exc:
            logging.warning("Codex start alert not delivered: %s", exc)
    return sent
