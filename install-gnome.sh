#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
TARGET="$HOME/.local/share/gnome-shell/extensions/codex-monitor@local"
mkdir -p "$(dirname "$TARGET")"
mkdir -p "$TARGET"
cp "$ROOT/gnome-extension/codex-monitor@local/metadata.json" "$ROOT/gnome-extension/codex-monitor@local/extension.js" "$ROOT/gnome-extension/codex-monitor@local/backend.py" "$ROOT/ntfy_settings.py" "$ROOT/ntfy_notifier.py" "$ROOT/activity_metadata.py" "$TARGET/"
printf 'Installed: %s\n' "$TARGET"
printf 'GNOME Shell on Wayland caches extension JavaScript until the next login.\n'
printf 'After finishing active work, log out and log back in to load updated extension.js.\n'
printf 'Do NOT log out while important Codex processes are running.\n'
