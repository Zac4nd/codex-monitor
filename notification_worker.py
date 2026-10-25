"""Consume persisted Codex lifecycle events and send opt-in notifications."""
import json
import logging
from pathlib import Path
from ntfy_notifier import publish
from ntfy_settings import read

def drain(events_path, cursor_path, sender=publish, config=None):
    config = read() if config is None else config
    if not config.get("enabled"):
        return 0
    events_path = Path(events_path)
    cursor_path = Path(cursor_path)
    if not events_path.exists():
        return 0
    # When enabling for the first time, skip historical events.
    if not cursor_path.exists():
        cursor_path.write_text(str(events_path.stat().st_size))
        return 0
    try:
        offset = int(cursor_path.read_text())
    except (OSError, ValueError):
        raise RuntimeError("Invalid notification cursor; refusing replay")
    if offset > events_path.stat().st_size:
        raise RuntimeError("Event log truncated; refusing automatic replay")
    sent = 0
    with events_path.open("rb") as stream:
        stream.seek(offset)
        while True:
            line = stream.readline()
            if not line:
                break
            if not line.endswith(b"\n"):
                break
            event = json.loads(line)
            # Commit cursor before sending: at-most-once attempt, not exactly-once delivery.
            cursor_path.write_text(str(stream.tell()))
            if event.get("event") != "finished" or event.get("ignored") or event.get("managed"):
                continue
            try:
                result = sender(event, config)
                sent += int(bool(result.get("sent")))
            except Exception as exc:
                logging.warning("ntfy delivery failed for PID %s: %s", event.get("pid"), exc)
    return sent
