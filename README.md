# Codex Monitor

Small, always-on-top PyQt6 widget for monitoring local Codex CLI executions on Linux.

- Green when no monitored executions are active; red otherwise.
- Expand with ▾ to inspect PID, project, elapsed time and command.
- Right-click any execution to ignore it without terminating it.
- Restore exclusions with the button in expanded view.
- Refreshes every 1.5 seconds; persistent Codex app servers are excluded.

## Requirements

Linux with `/proc`, Python 3, PyQt6 (`sudo apt install python3-pyqt6` on Debian).

## Usage

Run `./run.sh` or `python3 monitor.py`; use `python3 monitor.py --check` for a process scan.

Ignored process identities are stored in `~/.local/share/codex-monitor/ignored.json` and expire after their processes finish.

## GNOME Shell 48 extension

For a top-bar indicator rather than the floating PyQt widget:

```bash
./install-gnome.sh
```

After installing a new extension, **log out and back in** if GNOME does not yet recognize it. Then enable it with:

```bash
gnome-extensions enable codex-monitor@local
```

Click `● Codex 0` in the top-right panel to see the process list; click an active process to ignore it, or an ignored process to restore it. Ignored executions are shown in red at the bottom and do not affect the active count. The extension and the PyQt widget share the same ignored-process JSON file. You can disable it using `gnome-extensions disable codex-monitor@local`.

The extension uses a Python 3 `/proc` backend and requires no PyQt package. GNOME Shell 48 is the tested target version for installation and syntax; interactive GNOME activation still needs to be verified after login.

## Execution tracking and notifications (experimental)

The GNOME indicator and PyQt widget are unchanged. The new tracking components
are **not running as a service yet** and no network notifications are enabled.

- `execution_tracker.py` observes local CLI processes and stores state under
  `~/.local/share/codex-monitor/executions.json`, with events appended to `events.jsonl`.
  Use `python3 execution_tracker.py --once` for a single local observation, or run
  it as a foreground loop for development.
- `event_classifier.py` recognizes explicit `turn.completed`, `turn.failed` and
  `error` messages from a **specifically associated** Codex JSON event stream.
  An observed process disappearing remains `unknown` until a trustworthy
  source establishes its outcome. No automatic log-to-PID correlation yet.
- `ntfy_notifier.py` contains a prepared opt-in HTTPS transport targeting
  `https://ntfy.sh`. Its configuration has `enabled: false` by default.
  Neither the tracker nor the widget calls the transport yet.
- `python3 -m unittest -v test_monitor_events` runs the local synthetic tests.

**Limitations:** The tracker must be running continuously to notice process
transitions. A process disappearing between polls may be missed if it was never
observed. The classifier does not equate a Codex turn completing with all tests
passing. Waiting for approval or detecting stalled work is not implemented yet.

## Limitations

Process-based detection cannot determine actual task progress or success. Codex app-server sessions are not counted.
