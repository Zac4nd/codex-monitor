import json
import tempfile
import unittest
from pathlib import Path
from notification_worker import drain

class NotificationTests(unittest.TestCase):
    def test_at_most_once_and_ignored(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            events = root / "events.jsonl"
            cursor = root / "cursor.txt"
            records = [
                {"event":"started","identity":"1:1"},
                {"event":"finished","identity":"1:1","project":"demo","outcome":"unknown"},
                {"event":"finished","identity":"2:2","ignored":True},
            ]
            events.write_text("".join(json.dumps(x)+"\n" for x in records))
            cursor.write_text("0")
            calls = []
            sender = lambda e, c: (calls.append(e), {"sent": True})[1]
            cfg = {"enabled":True}
            self.assertEqual(drain(events,cursor,sender,cfg),1)
            self.assertEqual(drain(events,cursor,sender,cfg),0)
            self.assertEqual(len(calls),1)
    def test_completion_preference_and_activity(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder); events = root / "events"; cursor = root / "cursor"
            events.write_text(json.dumps({"event":"finished", "outcome":"unknown", "identity":"123:45", "project":"TeikosFSM", "activity":"SPEC-018 · Drag interventi"}) + "\n")
            cursor.write_text("0")
            sent=[]
            sender=lambda e,c: (sent.append(e), {"sent":True})[1]
            self.assertEqual(drain(events,cursor,sender,{"enabled":True,"notify_complete":False}),0)
            self.assertEqual(drain(events,cursor,sender,{"enabled":True,"notify_complete":True}),0)
            self.assertEqual(sent,[])
            with events.open("a") as stream:
                stream.write(json.dumps({"event":"finished", "outcome":"unknown", "identity":"456:78", "project":"TeikosFSM", "activity":"SPEC-018 · Drag interventi"})+"\n")
            self.assertEqual(drain(events,cursor,sender,{"enabled":True,"notify_complete":True}),1)
            from ntfy_notifier import prepare
            self.assertEqual(prepare(sent[0],{})["title"],"Codex terminato")
            self.assertIn("SPEC-018",prepare(sent[0],{})["body"])
            self.assertEqual(drain(events,cursor,sender,{"enabled":True}),0)

    def test_disabled_does_not_advance(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); events=root/"e"; cursor=root/"c"
            events.write_text('{"event":"finished"}\n')
            self.assertEqual(drain(events,cursor,config={"enabled":False}),0)
            self.assertFalse(cursor.exists())
    def test_first_activation_skips_history(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); events=root/"e"; cursor=root/"c"
            events.write_text('{"event":"finished"}\n')
            self.assertEqual(drain(events,cursor,config={"enabled":True}),0)
            self.assertEqual(int(cursor.read_text()),events.stat().st_size)

if __name__=="__main__":
    unittest.main()
