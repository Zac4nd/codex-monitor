#!/usr/bin/env python3
"""GNOME Shell Codex Monitor helper. JSON only; no GUI dependencies."""
import json
import os
import sys
from pathlib import Path

STORE = Path.home() / ".local/share/codex-monitor/ignored.json"

def identity(pid):
    try:
        return f"{pid}:" + Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19]
    except (OSError, IndexError):
        return ""

def ignored_ids():
    try:
        return set(json.loads(STORE.read_text()))
    except (OSError, ValueError, TypeError):
        return set()

def save(ids):
    STORE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STORE.with_suffix(".tmp")
    tmp.write_text(json.dumps(sorted(ids), indent=2))
    tmp.replace(STORE)

def scan():
    result = []
    for path in Path("/proc").iterdir():
        if not path.name.isdigit():
            continue
        try:
            args = [a.decode("utf-8", "replace") for a in (path / "cmdline").read_bytes().split(b"\0") if a]
            if not args or os.path.basename(args[0]) != "codex":
                continue
            if any(a in ("app-server", "exec-server", "mcp-server", "code-mode-host") for a in args[1:]):
                continue
            if not ("exec" in args[1:] or "resume" in args[1:] or len(args) == 1):
                continue
            pid = int(path.name)
            key = identity(pid)
            if not key:
                continue
            stat = (path / "stat").read_text().rsplit(")", 1)[1].split()
            uptime = float(Path("/proc/uptime").read_text().split()[0])
            elapsed = max(0, int(uptime - int(stat[19]) / os.sysconf("SC_CLK_TCK")))
            result.append(dict(pid=pid, identity=key, project=os.path.basename(os.readlink(path / "cwd")),
                               seconds=elapsed, command=" ".join(args[1:]) or "interactive"))
        except (OSError, ValueError, IndexError):
            continue
    return sorted(result, key=lambda p: p["pid"])

def main():
    command = sys.argv[1] if len(sys.argv) > 1 else "list"
    ids = ignored_ids()
    if command in ("ignore", "restore"):
        if len(sys.argv) != 3:
            raise ValueError("Expected PID and identity")
        pid = int(sys.argv[2].split(":", 1)[0])
        key = identity(pid)
        if not key or key != sys.argv[2]:
            raise ValueError("Process no longer exists")
        if command == "ignore":
            ids.add(key)
        else:
            ids.discard(key)
        save(ids)
    elif command == "restore-all":
        ids.clear()
        save(ids)
    elif command != "list":
        raise ValueError("Unknown command")
    procs = scan()
    alive = {p["identity"] for p in procs}
    if ids - alive:
        ids.intersection_update(alive)
        save(ids)
    active, ignored = [], []
    for proc in procs:
        proc["ignored"] = proc["identity"] in ids
        (ignored if proc["ignored"] else active).append(proc)
    print(json.dumps(dict(active=active, ignored=ignored)))

if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps(dict(error=str(exc))))
        sys.exit(1)
