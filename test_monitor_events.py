import unittest
from unittest.mock import patch
from execution_tracker import observe
from event_classifier import classify_jsonl, reconcile_finished
from ntfy_notifier import publish, prepare, DEFAULT_CONFIG

class TrackerTests(unittest.TestCase):
    def test_start_then_finish_unknown(self):
        p = dict(pid=123, identity="123:456", project="AZFlow", command="exec")
        state, events = observe(snapshot=[p], previous={}, now="T1")
        self.assertEqual([e["event"] for e in events], ["started"])
        state, events = observe(snapshot=[], previous=state, now="T2")
        self.assertEqual(events[0]["outcome"], "unknown")
    def test_no_duplicate_start(self):
        p = dict(pid=123, identity="123:456", project="AZFlow", command="exec")
        state, _ = observe(snapshot=[p], previous={}, now="T1")
        _, events = observe(snapshot=[p], previous=state, now="T2")
        self.assertEqual(events, [])
    def test_pid_reuse_new_identity(self):
        old = dict(pid=123, identity="123:1", project="old", command="exec")
        new = dict(pid=123, identity="123:2", project="new", command="exec")
        state, _ = observe(snapshot=[old], previous={}, now="T1")
        _, events = observe(snapshot=[new], previous=state, now="T2")
        self.assertEqual(set(e["event"] for e in events), {"started", "finished"})

class EventsTests(unittest.TestCase):
    def test_completed(self):
        self.assertEqual(classify_jsonl(['{"type":"turn.completed"}']), "completed")
    def test_failed(self):
        self.assertEqual(classify_jsonl(['{"type":"turn.failed"}']), "failed")
    def test_unknown(self):
        self.assertEqual(classify_jsonl(['{"type":"item.completed"}']), "unknown")
    def test_invalid(self):
        self.assertEqual(classify_jsonl(["invalid"]), "unknown")

class NtfyTests(unittest.TestCase):
    @patch("ntfy_notifier.urlopen")
    def test_default_never_networks(self, opener):
        result = publish({"event":"finished","project":"AZFlow"}, DEFAULT_CONFIG)
        self.assertFalse(result["sent"])
        opener.assert_not_called()
    def test_minimum_payload(self):
        data = prepare({"event":"finished", "outcome":"completed", "project":"AZFlow",
                        "command":"secret", "identity":"test"}, {})
        self.assertEqual(data["body"], "AZFlow")

if __name__ == "__main__":
    unittest.main()
