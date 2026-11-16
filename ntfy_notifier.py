"""Opt-in ntfy HTTP transport. Disabled by default. No third-party dependencies."""
import json
import os
from urllib.request import Request, urlopen
from activity_metadata import clean_label

def prepare(event, config):
    """Create only minimal, non-sensitive notification data."""
    if event.get("event") == "started":
        project = clean_label(event.get("project", "")) or "Progetto"
        activity = clean_label(event.get("activity", ""))
        return {"title": "Codex: turno avviato",
                "body": project + (" · " + activity if activity else ""), "priority": "3"}
    if event.get("event") != "finished":
        return None
    state = event.get("outcome", "unknown")
    title = {"completed": "Codex terminato", "failed": "Codex terminato (errore)",
             "unknown": "Codex terminato"}.get(state)
    if not title:
        return None
    project = clean_label(event.get("project", "")) or "Progetto"
    activity = clean_label(event.get("activity", ""))
    body = project + (" · " + activity if activity else "")
    return {"title": title, "body": body, "priority": "4" if state == "failed" else "3"}

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
