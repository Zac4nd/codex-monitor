import unittest
from unittest.mock import patch
from codex_monitor_exec import run
from execution_tracker import observe

class VerifiedOutcomeTests(unittest.TestCase):
    @patch("codex_monitor_exec.subprocess.call", return_value=0)
    def test_success(self, call):
        sent=[]
        code=run(["exec","-s","read-only","test"],sender=lambda e,c: sent.append(e),config={"enabled":True})
        self.assertEqual(code,0)
        self.assertEqual(sent[0]["outcome"],"completed")
        self.assertEqual(call.call_args.kwargs["env"]["CODEX_MONITOR_WRAPPED"],"1")
    @patch("codex_monitor_exec.subprocess.call", return_value=7)
    def test_error(self, call):
        sent=[]
        code=run(["exec","test"],sender=lambda e,c: sent.append(e),config={"enabled":True})
        self.assertEqual(code,7)
        self.assertEqual(sent[0]["outcome"],"failed")
    def test_managed_flag_persisted(self):
        p=dict(pid=10,identity="10:22",project="X",command="exec",managed=True)
        state,_=observe(snapshot=[p],previous={},now="T1")
        _,ev=observe(snapshot=[],previous=state,now="T2")
        self.assertTrue(ev[0]["managed"])

if __name__ == "__main__": unittest.main()
