#!/usr/bin/env python3
"""Persistent process observation without assuming that disappearance means success."""
import argparse
import importlib.util
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = Path(os.environ.get("CODEX_MONITOR_DATA_DIR", Path.home() / ".local/share/codex-monitor"))
STATE = DATA / "executions.json"
EVENTS = DATA / "events.jsonl"

def backend_scan():
    target = HERE / "gnome-extension/codex-monitor@local/backend.py"
    spec = importlib.util.spec_from_file_location("codex_monitor_backend", target)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    ignored = mod.ignored_ids()
    processes = mod.scan()
    for process in processes:
        process['ignored'] = process['identity'] in ignored
    return processes

def atomic_write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    try:
        tmp.write_text(json.dumps(payload, indent=2) + "\n")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)

def load_state():
    try:
        data = json.loads(STATE.read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}

def observe(snapshot=None, now=None, previous=None):
    """Pure transition logic: only sessions already observed can produce a finish event."""
    now = now or datetime.now(timezone.utc).isoformat()
    previous = {} if previous is None else previous
    snapshot = backend_scan() if snapshot is None else snapshot
    current = {p["identity"]: p for p in snapshot}
    events = []
    next_state = {}
    for key, p in current.items():
        old = previous.get(key)
        if not old:
            events.append({"event": "started", "identity": key, "pid": p["pid"], "project": p["project"], "at": now})
        next_state[key] = {"pid": p["pid"], "project": p["project"], "command": p["command"],
                           "first_seen": old.get("first_seen", now) if old else now,
                           "last_seen": now, "ignored": p.get("ignored", False),
                           "managed": p.get("managed", False)}
    for key, p in previous.items():
        if key not in current:
            events.append({"event": "finished", "outcome": "unknown", "identity": key,
                           "pid": p["pid"], "project": p["project"], "at": now,
                           "ignored": p.get("ignored", False), "managed": p.get("managed", False)})
    return next_state, events

def tick():
    DATA.mkdir(parents=True, exist_ok=True)
    import fcntl
    with (DATA / "tracker.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state, events = observe(previous=load_state())
        # Persist events before snapshot: duplicates are possible after a crash, but no guessed outcomes.
        with EVENTS.open("a") as stream:
            for event in events:
                stream.write(json.dumps(event, ensure_ascii=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        atomic_write(STATE, state)
    return events

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Single observation; no notifications")
    parser.add_argument("--interval", type=float, default=2.0)
    args = parser.parse_args()
    if args.once:
        print(json.dumps(tick(), ensure_ascii=False))
    else:
        from notification_worker import drain
        while True:
            tick()
            drain(EVENTS, DATA / 'notification-cursor.txt')
            time.sleep(max(0.5, args.interval))
