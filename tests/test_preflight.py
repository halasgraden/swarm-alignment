import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from swarm_lab.batch import main

class BadPolicy:
    def __init__(self,*a,**kw): self.last_response=None
    def metadata(self): return {'model':{'digest':'abc'},'ollama':{'version':'test'}}
    def __call__(self, obs, rng):
        self.last_response={'response':{'done_reason':'length','message':{'content':'','thinking':'partial'}},'request':{}}
        return {'action':'invalid_model_response'}

class PreflightTests(unittest.TestCase):
    def test_truncated_response_aborts_before_runs(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d); conf=path/'config.json'; out=path/'batch'
            conf.write_text(json.dumps({'agents':2,'task_count':4,'seeded_tasks':1,'actions_per_agent':4,'starting_points':0,'reward':'individual','elimination':False,'inference':{'model':'fake'}}))
            args=['batch','--config',str(conf),'--output',str(out),'--seeds','1','--scarce','4','--plentiful','6']
            with patch.object(sys,'argv',args),patch('swarm_lab.ollama.OllamaPolicy',BadPolicy):
                with self.assertRaisesRegex(RuntimeError,'preflight'): main()
            self.assertTrue((out/'preflight.json').exists())
            self.assertFalse(any(p.is_dir() for p in out.iterdir()))
class ReasoningPreflightTests(unittest.TestCase):
    def test_missing_reasoning_aborts(self):
        class NoReasoning:
            def __init__(self,*args,**kwargs): self.last_response=None
            def metadata(self): return {'backend':'openrouter','model':{'id':'fake'}}
            def __call__(self, obs, rng):
                self.last_response={'response':{'done_reason':'stop','message':{'content':'{\"action\":\"pass\"}'},'raw':{'provider':'host','model':'fake'}},'request':{}}
                return {'action':'pass'}
        with tempfile.TemporaryDirectory() as d:
            path=Path(d); conf=path/'config.json'; out=path/'batch'
            conf.write_text(json.dumps({'agents':2,'task_count':4,'seeded_tasks':1,'actions_per_agent':4,'starting_points':0,'reward':'individual','elimination':False,'inference':{'backend':'openrouter','model':'fake','require_reasoning':True}}))
            args=['batch','--config',str(conf),'--output',str(out),'--seeds','1','--scarce','4','--plentiful','6']
            with patch.object(sys,'argv',args),patch('swarm_lab.openrouter.OpenRouterPolicy',NoReasoning):
                with self.assertRaisesRegex(RuntimeError,'no readable reasoning'): main()
            self.assertFalse(json.loads((out/'preflight.json').read_text())['visible_reasoning'])
class ProviderChangeTests(unittest.TestCase):
    def test_provider_switch_marks_run_invalid(self):
        class ChangingProvider:
            def __init__(self,*args,**kwargs): self.last_response=None;self.n=0
            def metadata(self): return {'backend':'openrouter','model':{'id':'fake'}}
            def __call__(self,obs,rng):
                self.n+=1; provider='first' if self.n==1 else 'second'
                self.last_response={'response':{'done_reason':'stop','message':{'thinking':'visible reasoning'},'raw':{'provider':provider,'model':'fake'}},'request':{}}
                return {'action':'pass'}
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); conf=root/'c.json';out=root/'batch'
            conf.write_text(json.dumps({'agents':2,'task_count':4,'seeded_tasks':1,'actions_per_agent':4,'starting_points':0,'reward':'individual','elimination':False,'inference':{'backend':'openrouter','model':'fake','require_reasoning':True}}))
            args=['batch','--config',str(conf),'--output',str(out),'--seeds','1','--scarce','4','--plentiful','6']
            with patch.object(sys,'argv',args),patch('swarm_lab.openrouter.OpenRouterPolicy',ChangingProvider):
                with self.assertRaisesRegex(RuntimeError,'Provider or returned model changed'): main()
            manifests=list(out.glob('*/manifest.json'))
            self.assertEqual(len(manifests),1)
            self.assertEqual(json.loads(manifests[0].read_text())['status'],'invalid_provider_or_model')
if __name__=='__main__': unittest.main()
