#!/usr/bin/env python3
"""Shared ntfy settings: CLI and compact PyQt editor."""
import argparse
import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit
from ntfy_notifier import publish

PATH = Path.home() / ".config/codex-monitor/ntfy.json"
DEFAULT = {"enabled": False, "url": "https://ntfy.sh", "topic": ""}
TOPIC = re.compile(r"^[A-Za-z0-9_-]{1,128}$")

def read():
    try:
        value = json.loads(PATH.read_text())
        return {**DEFAULT, **value}
    except (OSError, ValueError):
        return DEFAULT.copy()

def save(data):
    url = str(data["url"]).rstrip("/")
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ("", "/"):
        raise ValueError("Server must be an HTTPS origin without credentials or path")
    topic = str(data["topic"])
    if topic and not TOPIC.fullmatch(topic):
        raise ValueError("Topic accepts only letters, digits, - and _ (max 128)")
    if data["enabled"] and not topic:
        raise ValueError("Topic required before enabling notifications")
    PATH.parent.mkdir(parents=True, exist_ok=True)
    temp = PATH.with_suffix(".tmp")
    temp.write_text(json.dumps({"enabled": bool(data["enabled"]), "url": url, "topic": topic}, indent=2) + "\n")
    os.chmod(temp, 0o600)
    os.replace(temp, PATH)

def gui():
    from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QFormLayout, QLineEdit, QCheckBox, QPushButton, QMessageBox
    app = QApplication.instance() or QApplication([])
    window = QWidget()
    window.setWindowTitle("Codex Monitor — Notifiche ntfy")
    root = QVBoxLayout(window)
    form = QFormLayout()
    state = read()
    url = QLineEdit(state["url"])
    topic = QLineEdit(state["topic"])
    enabled = QCheckBox("Abilita invio (quando collegato al tracker)")
    enabled.setChecked(state["enabled"])
    form.addRow("Server HTTPS:", url)
    form.addRow("Topic:", topic)
    form.addRow("", enabled)
    root.addLayout(form)
    def values():
        return {"url": url.text().strip(), "topic": topic.text().strip(), "enabled": enabled.isChecked()}
    def store():
        try:
            save(values())
            QMessageBox.information(window, "Codex Monitor", "Configurazione salvata.")
        except ValueError as exc:
            QMessageBox.warning(window, "Configurazione non valida", str(exc))
    def test():
        try:
            config = values()
            config["enabled"] = True
            # Explicit click: one harmless test notification.
            result = publish({"event":"finished","outcome":"unknown","project":"Test manuale Codex Monitor"}, config)
            QMessageBox.information(window, "Test ntfy", f"Invio accettato: {result}")
        except Exception as exc:
            QMessageBox.warning(window, "Test ntfy fallito", str(exc))
    save_button = QPushButton("Salva")
    test_button = QPushButton("Invia notifica di prova")
    save_button.clicked.connect(store)
    test_button.clicked.connect(test)
    root.addWidget(save_button)
    root.addWidget(test_button)
    window.resize(450, 180)
    window.show()
    return app.exec()

def main():
    p = argparse.ArgumentParser()
    subs = p.add_subparsers(dest="action")
    subs.add_parser("show")
    edit = subs.add_parser("set")
    edit.add_argument("--topic")
    edit.add_argument("--url")
    toggle = subs.add_parser("enable")
    subs.add_parser("disable")
    subs.add_parser("test")
    subs.add_parser("gui")
    args = p.parse_args()
    if args.action == "gui":
        return gui()
    if args.action == "show" or args.action is None:
        print(json.dumps(read(), indent=2))
    elif args.action == "set":
        data = read()
        if args.topic is not None: data["topic"] = args.topic
        if args.url is not None: data["url"] = args.url
        save(data)
        print("Saved")
    elif args.action in ("enable", "disable"):
        data = read()
        data["enabled"] = args.action == "enable"
        save(data)
        print("Saved")
    elif args.action == "test":
        data = read()
        data["enabled"] = True
        print(publish({"event":"finished","outcome":"unknown","project":"Test manuale Codex Monitor"}, data))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
