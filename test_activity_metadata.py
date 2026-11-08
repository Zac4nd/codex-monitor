"""Focused tests for conservative activity provenance, no cross-session guessing."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from activity_metadata import (extract_activity, clean_label, activity_for_session,
                               session_file_for_pid, explicit_label)
from ntfy_notifier import prepare
from session_events import collect
from execution_tracker import record_session_labels

class ActivityTests(unittest.TestCase):
    def test_explicit_title_and_conservative_fallback(self):
        self.assertEqual(extract_activity("SPEC-018 · Drag interventi\nProcedi."), "SPEC-018 · Drag interventi")
        self.assertEqual(extract_activity("SPEC-018 continuation — owner requests draggable events"),
                         "SPEC-018")
        self.assertIsNone(extract_activity("Please update the dashboard today"))
        self.assertIsNone(clean_label("token=secret123"))
        self.assertIsNone(clean_label("https://example.com/private"))
        self.assertIsNone(clean_label("/home/user/secret"))
    def test_independent_session_files_same_project(self):
        with tempfile.TemporaryDirectory() as root:
            base=Path(root); files=base/"sessions";files.mkdir()
            a=files/"a.jsonl"; b=files/"b.jsonl"
            def write(file,text):
                file.write_text(json.dumps({"type":"response_item","payload":{"type":"message","role":"user","content":[{"type":"input_text","text":text}]}})+"\n")
            write(a, "SPEC-018 · Drag interventi")
            write(b, "SPEC-019 · Fatturazione")
            proc=base/"proc"
            for pid,target in ((101,a),(102,b)):
                fd=proc/str(pid)/"fd";fd.mkdir(parents=True)
                (fd/"5").symlink_to(target)
            self.assertEqual(session_file_for_pid(101,files,proc),str(a))
            self.assertEqual(session_file_for_pid(102,files,proc),str(b))
            self.assertNotEqual(activity_for_session(a),activity_for_session(b))
            (proc/"101"/"fd"/"6").symlink_to(b)
            self.assertIsNone(session_file_for_pid(101,files,proc))
    def test_explicit_env_and_risk_filter(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/"201";path.mkdir()
            (path/"environ").write_bytes(b"FOO=1\0CODEX_MONITOR_ACTIVITY=SPEC-018 \xc2\xb7 Drag interventi\0")
            self.assertEqual(explicit_label(201,Path(root)), "SPEC-018 · Drag interventi")
    def test_session_only_and_notifications_are_minimal(self):
        with tempfile.TemporaryDirectory() as root:
            dir=Path(root)/"2026"/"11"/"08";dir.mkdir(parents=True)
            file=dir/"a.jsonl"
            payload=[
                {"type":"session_meta","payload":{"cwd":"/projects/TeikosFSM"}},
                {"type":"response_item","payload":{"type":"message","role":"user","content":[{"type":"input_text","text":"SPEC-018 · Drag interventi\nMy secret command should not appear: password=private"}]}},
                {"type":"event_msg","payload":{"type":"task_started"}},
                {"type":"event_msg","payload":{"type":"task_complete"}}]
            file.write_text("".join(json.dumps(x)+"\n" for x in payload))
            _,events=collect(Path(root),{}, {})
            self.assertEqual([e.get("activity") for e in events],["SPEC-018 · Drag interventi"]*2)
            for e in events:
                body=prepare(e,{})["body"]
                self.assertIn("SPEC-018 · Drag interventi",body)
                self.assertNotIn("private",body)
                self.assertNotIn("/projects",body)
    def test_two_turns_same_session_keep_distinct_titles(self):
        with tempfile.TemporaryDirectory() as root:
            day=Path(root)/"2026"/"11"/"08";day.mkdir(parents=True)
            file=day/"two.jsonl"
            def msg(text):
                return {"type":"response_item","payload":{"type":"message","role":"user",
                    "content":[{"type":"input_text","text":text}]}}
            def ev(kind):
                return {"type":"event_msg","payload":{"type":kind}}
            records=[ev("task_started"),msg("SPEC-018 · Drag interventi"),ev("task_complete"),
                     ev("task_started"),msg("SPEC-019 · Export contabile"),ev("task_complete")]
            file.write_text("".join(json.dumps(r)+"\n" for r in records))
            _,events=collect(Path(root),{}, {})
            self.assertEqual([e.get("activity") for e in events],
                ["SPEC-018 · Drag interventi"]*2 + ["SPEC-019 · Export contabile"]*2)
    def test_explicit_label_wins_for_correct_session(self):
        with tempfile.TemporaryDirectory() as root:
            f=Path(root)/"session-labels.json"
            with patch("execution_tracker.SESSION_LABELS",f):
                record_session_labels([{"session_file":"/a.jsonl","activity":"SPEC-018 · Drag interventi","activity_source":"explicit"}])
                self.assertEqual(json.loads(f.read_text()),{"/a.jsonl":"SPEC-018 · Drag interventi"})
                self.assertEqual(f.stat().st_mode & 0o777,0o600)
            self.assertEqual(prepare({"event":"started","project":"TeikosFSM",
                "activity":"SPEC-018 · Drag interventi","prompt":"Never send this"}, {})["body"],
                "TeikosFSM · SPEC-018 · Drag interventi")

if __name__=="__main__":
    unittest.main()
