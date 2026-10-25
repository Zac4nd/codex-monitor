#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
TARGET="$HOME/.local/share/gnome-shell/extensions/codex-monitor@local"
mkdir -p "$(dirname "$TARGET")"
mkdir -p "$TARGET"
cp "$ROOT/gnome-extension/codex-monitor@local/metadata.json" "$ROOT/gnome-extension/codex-monitor@local/extension.js" "$ROOT/gnome-extension/codex-monitor@local/backend.py" "$ROOT/ntfy_settings.py" "$ROOT/ntfy_notifier.py" "$TARGET/"
printf 'Installed: %s\n' "$TARGET"
printf 'GNOME Shell may require logout/login before newly installed extensions are discoverable.\n'
printf 'Then run: gnome-extensions enable codex-monitor@local\n'
