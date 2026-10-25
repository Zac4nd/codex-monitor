import json
import tempfile
import unittest
from pathlib import Path
from session_notifier import poll
from ntfy_notifier import prepare
from ntfy_settings import DEFAULT, save, read
from unittest.mock import patch

class NotificationPreferencesTests(unittest.TestCase):
    def test_all_three_filters_and_no_replay(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/"sessions"
            day=root/"2026"/"10"/"25"; day.mkdir(parents=True)
            state=Path(td)/"cursor"
            sent=[]
            sender=lambda e,c: (sent.append(e),{"sent":True})[1]
            assert poll(root,state,sender,{"enabled":True}) == 0
            path=day/"test.jsonl"
            records=[{"type":"session_meta","payload":{"cwd":"/work/Example"}},
                     *[{"type":"event_msg","payload":{"type":kind}} for kind in ("task_started","task_complete","turn_aborted","task_started")]]
            path.write_text("".join(json.dumps(x)+"\n" for x in records))
            cfg={"enabled":True, "notify_start":False, "notify_complete":True, "notify_error":False}
            self.assertEqual(poll(root,state,sender,cfg),1)
            self.assertEqual(sent[0]["outcome"],"completed")
            self.assertEqual(poll(root,state,sender,{"enabled":True}),0)
            with path.open("a") as f:
                f.write(json.dumps({"type":"event_msg","payload":{"type":"task_started"}})+"\n")
                f.write(json.dumps({"type":"event_msg","payload":{"type":"turn_aborted"}})+"\n")
            self.assertEqual(poll(root,state,sender,{"enabled":True,"notify_start":True,"notify_complete":False,"notify_error":True}),2)
            self.assertEqual([e["event"] for e in sent[1:]],["started","finished"])
    def test_start_payload(self):
        self.assertEqual(prepare({"event":"started","project":"Example"}, {})["title"],"Codex: turno avviato")
    def test_persistence_and_defaults(self):
        with tempfile.TemporaryDirectory() as td:
            with patch("ntfy_settings.PATH", Path(td)/"config.json"):
                data={**DEFAULT,"topic":"abc","enabled":True,"notify_start":False}
                save(data)
                self.assertFalse(read()["notify_start"])
                self.assertTrue(read()["notify_error"])
                self.assertEqual((Path(td)/"config.json").stat().st_mode & 0o777,0o600)

if __name__=="__main__":
    unittest.main()
