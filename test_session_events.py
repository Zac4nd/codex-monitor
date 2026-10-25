import json
import tempfile
import unittest
from pathlib import Path
from session_events import collect
from session_notifier import poll

class SessionLogTests(unittest.TestCase):
    def test_new_session_completion_once(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/"sessions"
            day=root/"2026"/"10"/"25"; day.mkdir(parents=True)
            state=Path(td)/"offsets.json"
            cfg={"enabled":True}
            sent=[]
            sender=lambda e,c: (sent.append(e),{"sent":True})[1]
            self.assertEqual(poll(root,state,sender,cfg),0)
            path=day/"rollout-test.jsonl"
            lines=[
              {"type":"session_meta","payload":{"cwd":"/tmp/demo"}},
              {"type":"event_msg","payload":{"type":"task_started"}},
              {"type":"event_msg","payload":{"type":"task_complete"}}]
            path.write_text("".join(json.dumps(item)+"\n" for item in lines))
            self.assertEqual(poll(root,state,sender,cfg),2)
            self.assertEqual(sent[0]["event"],"started")
            self.assertEqual(sent[1]["outcome"],"completed")
            self.assertEqual(sent[1]["project"],"demo")
            self.assertEqual(poll(root,state,sender,cfg),0)
    def test_existing_sessions_not_replayed(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/"s"; path=root/"2026"/"10"/"25";path.mkdir(parents=True)
            (path/"old.jsonl").write_text('{"type":"event_msg","payload":{"type":"task_complete"}}\n')
            state=Path(td)/"state"
            self.assertEqual(poll(root,state,config={"enabled":True}),0)
            self.assertEqual(poll(root,state,config={"enabled":True}),0)

if __name__=="__main__": unittest.main()
