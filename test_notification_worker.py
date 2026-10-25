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
