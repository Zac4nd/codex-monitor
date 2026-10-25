"""Opt-in ntfy HTTP transport. Disabled by default. No third-party dependencies."""
import json
import os
from urllib.request import Request, urlopen

def prepare(event, config):
    """Create only minimal, non-sensitive notification data."""
    if event.get("event") != "finished":
        return None
    state = event.get("outcome", "unknown")
    title = {"completed": "Codex: turno completato", "failed": "Codex: turno interrotto/errore",
             "unknown": "Codex terminato (esito sconosciuto)"}.get(state)
    if not title:
        return None
    project = str(event.get("project", "Progetto"))[:60]
    return {"title": title, "body": project, "priority": "4" if state == "failed" else "3"}

def publish(event, config):
    """Never send anything unless explicitly enabled by local config."""
    if not config.get("enabled", False):
        return {"sent": False, "reason": "disabled"}
    message = prepare(event, config)
    if not message:
        return {"sent": False, "reason": "unsupported_event"}
    url = str(config.get("url", "")).rstrip("/")
    if not url.startswith("https://"):
        raise ValueError("Only HTTPS ntfy endpoints are allowed")
    topic = str(config.get("topic", ""))
    if not topic or "/" in topic or len(topic) > 128:
        raise ValueError("Invalid ntfy topic")
    headers = {"Title": message["title"], "Priority": message["priority"],
               "Content-Type": "text/plain; charset=utf-8"}
    token = os.environ.get("CODEX_MONITOR_NTFY_TOKEN")
    if token:
        headers["Authorization"] = "Bearer " + token
    request = Request(url + "/" + topic, data=message["body"].encode(), headers=headers, method="POST")
    with urlopen(request, timeout=5) as response:
        return {"sent": True, "status": response.status}

DEFAULT_CONFIG = {"enabled": False, "url": "https://ntfy.sh", "topic": ""}
