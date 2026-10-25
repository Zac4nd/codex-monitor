#!/usr/bin/env python3
"""One-line always-on-top monitor for local Codex CLI executions."""
import os
import json
import sys
import time
from pathlib import Path
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMenu
)

IGNORE_FILE = Path.home() / ".local/share/codex-monitor/ignored.json"

def identity(pid):
    """Pair PID and kernel start ticks to avoid accidental exclusion on PID reuse."""
    try:
        return str(pid) + ":" + (Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[19])
    except (OSError, IndexError):
        return ""

def scan_codex():
    """Return CLI workers only; ignore VS Code / desktop app servers and Node shims."""
    found = []
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            raw = (proc / "cmdline").read_bytes()
            args = [a.decode("utf-8", "replace") for a in raw.split(b"\0") if a]
            if not args:
                continue
            exe = os.path.basename(args[0])
            if exe != "codex":
                continue
            # Ignore persistent Codex app backends.
            if any(a in ("app-server", "exec-server", "mcp-server", "code-mode-host") for a in args[1:]):
                continue
            # Node wrapper/desktop binaries excluded by executable basename above.
            # CLI 'exec' is the reliable unit-of-work signal; interactive bare 'codex' too.
            if not ("exec" in args[1:] or "resume" in args[1:] or len(args) == 1 or (len(args) > 1 and args[1].startswith("-"))):
                continue
            pid = int(proc.name)
            cwd = os.readlink(proc / "cwd")
            stat = (proc / "stat").read_text()
            after = stat.rsplit(")", 1)[1].split()
            ticks = os.sysconf("SC_CLK_TCK")
            uptime = float(Path("/proc/uptime").read_text().split()[0])
            elapsed = max(0, int(uptime - int(after[19]) / ticks))
            cmd = " ".join(args[1:])
            found.append((pid, cwd, elapsed, cmd if cmd else "interactive"))
        except (OSError, ValueError, IndexError, PermissionError):
            continue
    return sorted(found, key=lambda p: p[0])

def elapsed_str(seconds):
    h, m = divmod(seconds // 60, 60)
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

class Monitor(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Codex Monitor")
        self.setWindowFlags(Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setMinimumWidth(315)
        self.resize(370, 44)
        self.expanded = False
        try:
            self.ignored = set(json.loads(IGNORE_FILE.read_text()))
        except (OSError, ValueError):
            self.ignored = set()
        self.setStyleSheet("""
          QWidget { background: #20252b; color: #ffffff; font: 12px Sans; }
          QLabel#status { border-radius: 8px; padding: 6px 12px; font-weight: bold; }
          QPushButton { background: #424a55; color: white; border: 0; border-radius: 6px; padding: 5px 9px; }
          QPushButton:hover { background: #596373; }
          QTableWidget { background: #20252b; alternate-background-color: #2b323b; gridline-color: #41474f; }
          QHeaderView::section { background: #353e48; color: white; padding: 5px; border: 0; }
        """)
        root = QVBoxLayout(self)
        root.setContentsMargins(5, 5, 5, 5)
        root.setSpacing(4)
        bar = QHBoxLayout()
        self.status = QLabel("● Codex · verifica...")
        self.status.setObjectName("status")
        bar.addWidget(self.status, 1)
        self.settings_btn = QPushButton("⚙")
        self.settings_btn.setFixedWidth(32)
        self.settings_btn.clicked.connect(self.open_settings)
        bar.addWidget(self.settings_btn)
        self.toggle = QPushButton("▾")
        self.toggle.setFixedWidth(32)
        self.toggle.clicked.connect(self.toggle_details)
        bar.addWidget(self.toggle)
        self.close_btn = QPushButton("×")
        self.close_btn.setFixedWidth(32)
        self.close_btn.clicked.connect(self.close)
        bar.addWidget(self.close_btn)
        root.addLayout(bar)
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["PID", "Progetto", "Durata", "Comando"])
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 68)
        self.table.setColumnWidth(1, 130)
        self.table.setColumnWidth(2, 78)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setVisible(False)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_process_menu)
        self.restore_btn = QPushButton("Ripristina esclusi")
        self.restore_btn.clicked.connect(self.restore_ignored)
        self.restore_btn.setVisible(False)
        root.addWidget(self.restore_btn)
        root.addWidget(self.table)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(1500)
        self.refresh()

    def open_settings(self):
        import subprocess
        subprocess.Popen([sys.executable, str(Path(__file__).resolve().with_name("ntfy_settings.py")), "gui"])

    def toggle_details(self):
        self.expanded = not self.expanded
        self.table.setVisible(self.expanded)
        self.restore_btn.setVisible(self.expanded and bool(self.ignored))
        self.toggle.setText("▴" if self.expanded else "▾")
        if self.expanded:
            self.setMaximumHeight(16777215)
            self.resize(780, 270)
        else:
            # Hide expanded widgets and force Qt to recompute the compact height.
            self.layout().activate()
            compact_height = self.layout().sizeHint().height()
            self.setFixedHeight(compact_height)
            self.resize(370, compact_height)

    def save_ignored(self):
        IGNORE_FILE.write_text(json.dumps(sorted(self.ignored), indent=2))
        self.restore_btn.setVisible(self.expanded and bool(self.ignored))

    def ignore_pid(self, pid):
        key = identity(pid)
        if key:
            self.ignored.add(key)
            self.save_ignored()
            self.refresh()

    def restore_ignored(self):
        self.ignored.clear()
        self.save_ignored()
        self.refresh()

    def show_process_menu(self, pos):
        item = self.table.itemAt(pos)
        if item is None:
            return
        pid_item = self.table.item(item.row(), 0)
        if pid_item is None:
            return
        pid = int(pid_item.text())
        menu = QMenu(self)
        is_ignored = identity(pid) in self.ignored
        action = menu.addAction(
            f"Ripristina PID {pid}" if is_ignored else f"Ignora PID {pid} (non terminare)"
        )
        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))
        if chosen == action:
            if is_ignored:
                self.ignored.discard(identity(pid))
                self.save_ignored()
                self.refresh()
            else:
                self.ignore_pid(pid)

    def refresh(self):
        all_procs = scan_codex()
        alive = {identity(pid) for pid, *_ in all_procs}
        # Retain ignored processes while alive, clear after they exit.
        if self.ignored - alive:
            self.ignored.intersection_update(alive)
            self.save_ignored()
        active = [p for p in all_procs if identity(p[0]) not in self.ignored]
        ignored = [p for p in all_procs if identity(p[0]) in self.ignored]
        n = len(active)
        self.status.setText((f"● Codex · {n} attiv{'o' if n == 1 else 'i'}" if n else "● Codex · tutto fermo") + (f"  · {len(ignored)} ignorati" if ignored else ""))
        self.status.setStyleSheet(
            f"background: {'#9e3030' if n else '#1c7548'}; color: white;"
        )
        if self.expanded:
            procs = active + ignored
            self.table.setRowCount(len(procs))
            for row, (pid, cwd, elapsed, cmd) in enumerate(procs):
                is_ignored = row >= n
                values = (str(pid), os.path.basename(cwd), elapsed_str(elapsed),
                          ("[IGNORATO] " if is_ignored else "") + cmd)
                for col, value in enumerate(values):
                    item = QTableWidgetItem(value)
                    item.setToolTip(cwd if col == 1 else cmd if col == 3 else value)
                    if is_ignored:
                        item.setBackground(Qt.GlobalColor.darkRed)
                        item.setForeground(Qt.GlobalColor.white)
                    self.table.setItem(row, col, item)

if __name__ == "__main__":
    if "--check" in sys.argv:
        print(scan_codex())
    else:
        app = QApplication(sys.argv)
        w = Monitor()
        w.show()
        sys.exit(app.exec())
