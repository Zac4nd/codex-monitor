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
run independently as an enabled `systemd --user` service on Debian. Notifications are opt-in through shared ntfy settings.

- `execution_tracker.py` observes local CLI processes and stores state under
  `~/.local/share/codex-monitor/executions.json`, with events appended to `events.jsonl`.
  Use `python3 execution_tracker.py --once` for a single local observation, or run
  it as a foreground loop for development.
- `event_classifier.py` recognizes explicit `turn.completed`, `turn.failed` and
  `error` messages from a **specifically associated** Codex JSON event stream.
  An observed process disappearing remains `unknown` until a trustworthy
  source establishes its outcome. No automatic log-to-PID correlation yet.
- `ntfy_notifier.py` sends opt-in HTTPS notifications to `https://ntfy.sh`.
  The live tracker now uses `session_notifier.py` to read **Codex session JSONL**
  directly, keyed by session file and byte offset, with no speculative PID mapping.
  Explicit `task_complete` means **turn completed**, not guaranteed task/test success;
  explicit `turn_aborted` or `task_failed` means interrupted/failed if present.
  Events without a supported terminal marker produce no success/failure claim.
  Existing logs are skipped on initial activation; offsets are recorded before
  sending (at-most-once, with possible lost alerts on network failure).
  The passive process event log is still maintained but no longer sends
  duplicate unknown-outcome notifications.
- `python3 ntfy_settings.py gui` opens the shared notification settings window;
  the GNOME menu and PyQt widget also provide access. CLI commands:
  `python3 ntfy_settings.py show`, `set --topic TOPIC`, `enable`, `disable`, `test`.
  `test` deliberately sends one HTTP notification regardless of the saved enabled flag.
  Settings are stored in `~/.config/codex-monitor/ntfy.json` (mode 0600).
- `python3 -m unittest -v test_monitor_events` runs the local synthetic tests.
- `systemctl --user status codex-monitor-tracker.service` checks the service;
  `systemctl --user stop codex-monitor-tracker.service` stops it without stopping Codex.

**Limitations:** The tracker must be running continuously to notice process
transitions. A process disappearing between polls may be missed if it was never
observed. The classifier does not equate a Codex turn completing with all tests
passing. Waiting for approval or detecting stalled work is not implemented yet.

## Verified outcomes for `codex exec`

The passive process monitor cannot obtain the exit code of unrelated processes.
To get a **verified successful/failed** Android alert, run a task through the
optional launcher instead of calling `codex exec` directly:

```bash
python3 codex_monitor_exec.py exec -s read-only 'Your task here'
```

The launcher preserves Codex's exit code, delivers one ntfy alert if enabled,
and marks its child as managed so the passive tracker does not send a duplicate
`unknown` alert. Regular Codex sessions continue to be monitored as before;
their outcome remains `unknown`. This reports the CLI exit status, not whether
all application tests or requirements passed. It does not modify source files
or add third-party dependencies.

## Limitations

Process-based detection cannot determine actual task progress or success. Codex app-server sessions are not counted.
