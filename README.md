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

The extension uses a Python 3 `/proc` backend and requires no PyQt package. On GNOME Shell 48 **Wayland**, updating `extension.js` requires a logout/login to load fresh JavaScript; disabling/re-enabling the extension does not clear the module cache. Finish active Codex work before logging out, since a logout can terminate user processes. The backend can be updated independently and is live immediately; verify the three-line menu after a new login.

## Execution tracking and notifications (experimental)

The GNOME indicator displays compact per-process activity details; the PyQt widget remains unchanged. The tracking components
run independently as an enabled `systemd --user` service on Debian. Notifications are opt-in through shared ntfy settings.

- `execution_tracker.py` observes local CLI processes and stores state under
  `~/.local/share/codex-monitor/executions.json`, with events appended to `events.jsonl`.
  Use `python3 execution_tracker.py --once` for a single local observation, or run
  it as a foreground loop for development.
- `event_classifier.py` recognizes explicit `turn.completed`, `turn.failed` and
  `error` messages from a **specifically associated** Codex JSON event stream.
  An observed process disappearing remains `unknown` until a trustworthy
  source establishes its outcome. No automatic log-to-PID correlation yet.
- `ntfy_notifier.py` sends opt-in HTTPS notifications to the configured ntfy topic.
  `session_notifier.py` reads Codex session JSONL for structured `task_started`
  events, including multiple turns within a long-running interactive session.
  Codex can write `task_started` *before* the user mandate appears in JSONL.
  To avoid losing the activity (for example `SPEC-030`) from start alerts,
  the notifier briefly defers an unlabeled start until its own session/turn
  contains a user task; after 12 seconds it sends a project-only alert instead.
  Pending starts and JSONL cursors survive service restarts, without replaying
  older notifications. No previous turn or different project supplies a fallback
  activity label.
  **No terminal notification is inferred from `task_complete`: it describes a
  turn, not the Codex process lifecycle.** `notification_worker.py` consumes
  process-disappearance events persisted by `execution_tracker.py` and sends
  **Codex terminato** regardless of whether the task succeeded, failed or
  lacks a terminal session marker. The short activity label is only context,
  not a statement that the task is finished. `unknown` outcomes are never
  described as successful. Explicitly wrapped executions retain their verified
  exit-code notification and are excluded from the passive duplicate path.
  Process identity uses PID plus kernel start time, not PID alone. Events are
  consumed using persisted byte offsets, skipping history on first activation;
  there is one notification attempt per event (delivery can be lost on network
  failure). Ignored processes remain excluded from passive exit notifications.
- `python3 ntfy_settings.py gui` opens the shared notification settings window;
  the GNOME menu and PyQt widget also provide access. CLI commands:
  `python3 ntfy_settings.py show`, `set --topic TOPIC`, `enable`, `disable`, `test`.
  The GUI offers three independent checkboxes for turn start, process termination and
  error/interruption, all enabled by default; CLI equivalents are
  `set --notify-start on|off --notify-complete on|off --notify-error on|off`.
  Preferences are read on each polling cycle without a service restart.
  `test` deliberately sends one HTTP notification regardless of the saved enabled flag.
  Settings are stored in `~/.config/codex-monitor/ntfy.json` (mode 0600).
- `python3 -m unittest -q test_monitor_events test_notification_worker test_verified_outcomes test_session_events test_notification_preferences test_activity_metadata` runs the focused local synthetic tests.
- `systemctl --user status codex-monitor-tracker.service` checks the service;
  `systemctl --user stop codex-monitor-tracker.service` stops it without stopping Codex.

**Limitations:** The tracker must be running continuously to notice process
transitions. A process disappearing between polls may be missed if it was never
observed. The classifier does not equate a Codex turn completing with all tests
passing. Waiting for approval or detecting stalled work is not implemented yet.

## GNOME activity identification

GNOME displays three lines per process:

```text
TeikosFSM
SPEC-018 · Drag interventi
Exec · 00:58 · PID 2989405
```

The activity label has a strict source priority:

1. An explicit per-launch environment variable, e.g.:

   ```bash
   CODEX_MONITOR_ACTIVITY="SPEC-018 · Drag interventi" codex exec "..."
   ```

   No global Codex configuration is changed. The value is kept short (maximum
   65 characters) and validated before display or notification.
2. A precise association with the process's **open Codex session JSONL file**
   through `/proc/<pid>/fd`. Only that session's user-task text is inspected
   for a clear `SPEC-NNN` or a heading of the form
   `SPEC-018 · Drag interventi`. Multiple session files, missing permissions,
   or ambiguous headings result in no description, not a guessed one.
3. Without an activity, the second line says `Attività non identificata`.
   The project, process type, duration and PID remain visible.

Process identity is PID **plus kernel start time**, preventing PID reuse from
assigning a label to a different process. Two concurrent Codex tasks working on
the same project are never matched merely by directory name. The same
session-file association is used for activity metadata in ntfy start and
process-termination notifications. ntfy receives only the project name and validated short
label, not prompts, session paths or other task text. When an explicit launch
label is present, the tracker stores it keyed by session file in a local
`session-labels.json` file (permissions 0600).

This can identify terminal, ChatGPT-launched or VS Code-launched processes **if**
their native Codex process and session file are visible to the Debian user.
Remote/cloud-only sessions and long-lived app-server processes that are excluded
from process tracking are not covered. A generic task without a reliable
identifier remains unlabeled. A `SPEC-018` in the prompt without a trustworthy
title is shown as `SPEC-018`, rather than inventing a description.

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
