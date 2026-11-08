import json
import tempfile
from pathlib import Path
from swarm_lab.run import run
import os
import random
import unittest
from unittest.mock import patch
from swarm_lab.openrouter import OpenRouterPolicy
class Response:
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def read(self):
        return json.dumps({'model':'example','provider':'host','choices':[{'finish_reason':'stop','message':{'content':'{"action":"pass"}','reasoning':'analysis'}}], 'usage':{'prompt_tokens':10,'completion_tokens':20,'cost':0.001}}).encode()
class RouterTests(unittest.TestCase):
    @patch.dict(os.environ,{'OPENROUTER_API_KEY':'not-a-real-secret'})
    @patch('urllib.request.urlopen',return_value=Response())
    def test_auth_not_logged_response_and_usage_preserved(self,call):
        p=OpenRouterPolicy('example',provider='example-host')
        self.assertEqual(p({'agent':'A1'},random.Random(3)),{'action':'pass'})
        self.assertNotIn('not-a-real-secret',json.dumps(p.last_response))
        self.assertEqual(p.last_response['response']['message']['reasoning'],'analysis')
        self.assertEqual(p.last_response['response']['raw']['provider'],'host')
        self.assertFalse(p.last_response['request']['provider']['allow_fallbacks'])
        self.assertEqual(p.last_response['request']['reasoning'], {'enabled': True})
        self.assertEqual(p.last_response['response']['eval_count'],20)
    @patch.dict(os.environ,{'OPENROUTER_API_KEY':'not-a-real-secret'})
    @patch('urllib.request.urlopen',return_value=Response())
    def test_full_run_preserves_cost_and_reasoning_without_key(self,call):
        c={'agents':2,'task_count':2,'seeded_tasks':0,'actions_per_agent':2,'starting_points':0,'reward':'individual','elimination':False}
        with tempfile.TemporaryDirectory() as d:
            path=run(c,1,Path(d)/'run',OpenRouterPolicy('example'),'openrouter:example')
            usage=json.loads((path/'usage.json').read_text())
            self.assertEqual(usage['calls'],4)
            self.assertAlmostEqual(usage['reported_cost_usd'],0.004)
            self.assertEqual(usage['providers'],['host'])
            combined=''.join(x.read_text() for x in path.iterdir() if x.is_file())
            self.assertNotIn('not-a-real-secret',combined)
            self.assertIn('analysis',combined)
    @patch.dict(os.environ,{},clear=True)
    def test_missing_key(self):
        with self.assertRaisesRegex(RuntimeError,'OPENROUTER_API_KEY'): OpenRouterPolicy('example')
if __name__=='__main__':unittest.main()
