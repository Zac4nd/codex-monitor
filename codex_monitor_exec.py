#!/usr/bin/env python3
"""Opt-in Codex exec launcher with reliable exit code and single completion alert."""
import argparse
import os
import subprocess
import sys
from pathlib import Path
from ntfy_notifier import publish
from ntfy_settings import read

def run(args, codex="codex", sender=publish, config=None):
    if not args:
        raise ValueError("Provide codex exec arguments")
    if args[0] != "exec":
        raise ValueError("Only codex exec is supported")
    # The wrapper owns this subprocess and therefore observes its true exit code.
    try:
        env = os.environ.copy()
        env['CODEX_MONITOR_WRAPPED'] = '1'
        code = subprocess.call([codex, *args], env=env)
    except OSError as exc:
        print(f"Cannot launch Codex: {exc}", file=sys.stderr)
        code = 127
    state = "completed" if code == 0 else "failed"
    cfg = read() if config is None else config
    if cfg.get("enabled"):
        event = {"event": "finished", "outcome": state,
                 "project": Path.cwd().name, "exit_code": code}
        try:
            sender(event, cfg)
        except Exception as exc:
            print(f"ntfy alert failed: {exc}", file=sys.stderr)
    return code

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run codex exec and report verified exit code")
    parser.add_argument("args", nargs=argparse.REMAINDER)
    options = parser.parse_args()
    sys.exit(run(options.args))
