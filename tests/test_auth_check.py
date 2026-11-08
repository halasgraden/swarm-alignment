import io
import os
import random
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch
from swarm_lab.check_openrouter import check_key
from swarm_lab.openrouter import OpenRouterPolicy

class Accepted:
    status=200
    def __enter__(self): return self
    def __exit__(self,*args): pass

class AuthenticationTests(unittest.TestCase):
    @patch.dict(os.environ,{'OPENROUTER_API_KEY':'example-not-real'})
    @patch('urllib.request.urlopen',return_value=Accepted())
    def test_auth_check_does_not_print_key(self,request):
        ok,message=check_key()
        self.assertTrue(ok)
        self.assertNotIn('example-not-real',message)
        self.assertTrue(request.call_args.args[0].full_url.endswith('/api/v1/key'))
    @patch.dict(os.environ,{'OPENROUTER_API_KEY':'export OPENROUTER_API_KEY'})
    def test_whitespace_rejected_before_network(self):
        ok,message=check_key()
        self.assertFalse(ok)
        self.assertIn('whitespace',message)
    @patch.dict(os.environ,{'OPENROUTER_API_KEY':'example-not-real'})
    @patch('urllib.request.urlopen',side_effect=urllib.error.HTTPError('https://example.test',401,'Unauthorized',{},io.BytesIO()))
    def test_401_is_actionable_and_does_not_expose_key(self,request):
        ok,message=check_key()
        self.assertFalse(ok)
        self.assertIn('401',message)
        with self.assertRaisesRegex(RuntimeError,'check_openrouter') as exc:
            OpenRouterPolicy('example')({'agent':'A1'},random.Random(1))
        self.assertNotIn('example-not-real',str(exc.exception))
    def test_existing_run_cli_prints_clear_error_without_overwrite(self):
        root=Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as d:
            r=subprocess.run([sys.executable,'-m','swarm_lab.run','--config','configs/example.json','--seed','42','--output',d],cwd=root,capture_output=True,text=True)
            self.assertEqual(r.returncode,2)
            self.assertIn('Choose a new --output path',r.stderr)
            self.assertNotIn('Traceback',r.stderr)
if __name__=='__main__': unittest.main()
