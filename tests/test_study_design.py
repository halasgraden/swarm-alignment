import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from swarm_lab.run import run
from swarm_lab.backends import TeamPolicy
from swarm_lab.study import main

BASE={'scenario':'incident_response','agents':4,'task_count':6,'seeded_tasks':2,'actions_per_agent':6,'starting_points':0,'reward':'individual','elimination':True,'checkpoint_rounds':[1,3,5]}

class StudyTests(unittest.TestCase):
    def test_three_checkpoints_and_winner(self):
        for mode in ('random','ranked'):
            with tempfile.TemporaryDirectory() as d:
                a=run({**BASE,'checkpoint_mode':mode},8,Path(d)/'a')
                b=run({**BASE,'checkpoint_mode':mode},8,Path(d)/'b')
                records=[json.loads(x) for x in (a/'trajectory.jsonl').read_text().splitlines()]
                systems=[r for r in records if r['type']=='system']
                self.assertEqual([s['after_round'] for s in systems],[1,3,5])
                self.assertEqual([len(s['eligible']) for s in systems],[4,3,2])
                self.assertEqual(len([r for r in records if r['type']=='turn']),15)
                self.assertEqual(systems[-1]['winner'],[r for r in records if r['type']=='turn'][-1]['event']['agent'])
                self.assertEqual((a/'trajectory.jsonl').read_bytes(),(b/'trajectory.jsonl').read_bytes())
    def test_seeded_ties(self):
        from swarm_lab.engine import Environment
        a=Environment({**BASE,'checkpoint_mode':'ranked'},17)
        b=Environment({**BASE,'checkpoint_mode':'ranked'},17)
        self.assertEqual(a.eliminate(),b.eliminate())
        self.assertEqual(len(b.eliminate()['eligible']),3)
    def test_routing_actions_and_claims(self):
        class Fake:
            def __init__(self, model): self.model=model; self.last_response=None
            def __call__(self,obs,rng): self.last_response={'model':self.model}; return self.model
            def claim(self,obs,rng): return self(obs,rng)
        with patch('swarm_lab.backends.make_policy',side_effect=lambda x:Fake(x)):
            p=TeamPolicy({'A1':'one','A2':'two'})
            self.assertEqual(p({'agent':'A2'},None),'two')
            self.assertEqual(p.claim({'agent':'A1'},None),'one')
    def test_export_excludes_private_models(self):
        import sys
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'study'; out=Path(d)/'share.json'
            def call(*args):
                with patch.object(sys,'argv',['study',*args]): main()
            call('plan','--study',str(root),'--providers','p1,p2,p3,p4','--seeds','1')
            call('run','--study',str(root),'--mock','--limit','1')
            call('export','--study',str(root),'--output',str(out))
            content=out.read_text().lower()
            for value in ('qwen','deepseek','mistral','openrouter','p1','gpt-oss'): self.assertNotIn(value,content)
            self.assertEqual(json.loads(content)['runs'][0]['policy'],'mock')
            call('archive','--study',str(root),'--output',str(Path(d)/'archive.zip'))
if __name__=='__main__': unittest.main()
