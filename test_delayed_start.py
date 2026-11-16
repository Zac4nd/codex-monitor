"""Regression: Codex writes task_started before user mandate. Delay only that alert."""
import json
import tempfile
import unittest
from pathlib import Path
from session_notifier import poll

def event(kind):
    return {"type":"event_msg","payload":{"type":kind}}

def user(text):
    return {"type":"response_item","payload":{"type":"message","role":"user",
            "content":[{"type":"input_text","text":text}]}}

def append(path, records):
    with path.open("a") as stream:
        for record in records:
            stream.write(json.dumps(record)+"\n")

class DelayedStartTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        day = root/"sessions"/"2026"/"11"/"16"
        day.mkdir(parents=True)
        self.root = root/"sessions"
        self.path = day/"rollout-new.jsonl"
        self.state = root/"offsets.json"
        self.sent=[]
        self.sender=lambda event, config:(self.sent.append(dict(event)), {"sent":True})[1]
        self.config={"enabled":True,"notify_start":True}
        self.assertEqual(poll(self.root,self.state,self.sender,self.config,now=100),0)

    def test_mandate_arrives_after_start_and_restart(self):
        append(self.path,[{"type":"session_meta","payload":{"cwd":"/projects/TeikosFSM"}},event("task_started")])
        self.assertEqual(poll(self.root,self.state,self.sender,self.config,now=101),0)
        self.assertEqual(self.sent,[])
        # Simulate a process restart by re-reading the pending state file.
        append(self.path,[user("# AGENTS.md instructions\nnot a real prompt"),
                          user("SPEC-030 · Outlook calendar synchronization")])
        self.assertEqual(poll(self.root,self.state,self.sender,self.config,now=102),1)
        self.assertEqual(len(self.sent),1)
        self.assertEqual(self.sent[0]["activity"],"SPEC-030 · Outlook calendar synchronization")
        self.assertEqual(poll(self.root,self.state,self.sender,self.config,now=103),0)

    def test_missing_spec_keeps_project_only(self):
        append(self.path,[event("task_started")])
        self.assertEqual(poll(self.root,self.state,self.sender,self.config,now=101),0)
        append(self.path,[user("Please inspect error logs without accessing secrets")])
        self.assertEqual(poll(self.root,self.state,self.sender,self.config,now=102),1)
        self.assertNotIn("activity",self.sent[0])

    def test_never_borrow_previous_turn_spec(self):
        append(self.path,[event("task_started"),user("SPEC-018 · Drag interventi"),event("task_complete")])
        self.assertEqual(poll(self.root,self.state,self.sender,self.config,now=101),1)
        append(self.path,[event("task_started")])
        self.assertEqual(poll(self.root,self.state,self.sender,self.config,now=102),0)
        append(self.path,[user("Check general health of the application")])
        self.assertEqual(poll(self.root,self.state,self.sender,self.config,now=103),1)
        self.assertNotIn("activity",self.sent[-1])

    def test_timeout_fallback_once(self):
        append(self.path,[event("task_started")])
        self.assertEqual(poll(self.root,self.state,self.sender,self.config,now=101),0)
        self.assertEqual(poll(self.root,self.state,self.sender,self.config,now=114),1)
        self.assertEqual(poll(self.root,self.state,self.sender,self.config,now=115),0)
        self.assertEqual(len(self.sent),1)

if __name__=="__main__":
    unittest.main()
