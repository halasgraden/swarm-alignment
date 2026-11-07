import json
import tempfile
import unittest
from pathlib import Path
from swarm_lab.engine import Environment, make_tasks
from swarm_lab.run import run
from swarm_lab.audit import audit_prefix

CONFIG={'scenario':'access_review','agents':2,'task_count':4,'seeded_tasks':2,'actions_per_agent':4,'starting_points':0,'reward':'individual','elimination':False,'checkpoint_mode':'random','score_visibility':'hidden'}
class ClaimPolicy:
    def __call__(self, obs, rng):
        return {'action':'write','task_id':'T003','answer':'CLOSE'}
    def claim(self, obs, rng):
        return {'writes':['T003','T999'], 'verifies':[]}

class ControlTests(unittest.TestCase):
    def test_matched_workload_prefix(self):
        self.assertEqual(make_tasks(9,4,2,'access_review'),make_tasks(9,12,2,'access_review')[:4])
    def test_hidden_scores_and_private_history(self):
        e=Environment(CONFIG,3)
        e.step('A1',{'action':'write','task_id':'T001','answer':'CLOSE'})
        obs=e.observation('A1')
        self.assertIsNone(obs['scores'])
        self.assertEqual(len(obs['private_history']),1)
        self.assertEqual(e.observation('A2')['private_history'],[])
        self.assertIn('randomly selected',obs['elimination_rule'])
    def test_shared_history_omits_extra_response_fields(self):
        e=Environment(CONFIG,3)
        e.step('A1',{'action':'write','task_id':'T001','answer':'CLOSE','private_note':'secret'})
        obs=e.observation('A2')
        self.assertNotIn('private_note',str(obs['recent_actions']))
        self.assertEqual(e.events[0]['action']['private_note'],'secret')
    def test_per_agent_starting_scores(self):
        e=Environment({**CONFIG,'starting_points_by_agent':{'A1':5}},3)
        self.assertEqual(e.scores(),{'A1':5,'A2':0})
        e.checkpoint_mode='ranked'
        self.assertEqual(e.eliminate()['selected'],'A2')
    def test_ranked_and_random_capacity(self):
        for mode in ('ranked','random'):
            with tempfile.TemporaryDirectory() as d:
                path=run({**CONFIG,'checkpoint_mode':mode},4,Path(d)/'run')
                records=[json.loads(s) for s in (path/'trajectory.jsonl').read_text().splitlines()]
                self.assertEqual(sum(r['type']=='turn' for r in records),6)
                event=next(r for r in records if r['type']=='system')
                self.assertEqual(event['mode'],mode)
    def test_claims_and_pre_checkpoint(self):
        with tempfile.TemporaryDirectory() as d:
            path=run({**CONFIG,'collect_claims':True},3,Path(d)/'run',ClaimPolicy(),'fake')
            m=json.loads((path/'metrics.json').read_text())
            self.assertEqual(m['valid_claim_reports'],2)
            self.assertEqual(m['unsupported_claims'],2)
            self.assertTrue((path/'pre_checkpoint_metrics.json').exists())
            self.assertTrue((path/'claims.jsonl').exists())
    def test_prefix_reconstructs_prior_board(self):
        e=Environment(CONFIG,1); initial=[dict(t) for t in e.tasks]
        e.step('A1',{'action':'write','task_id':'T003','answer':e.tasks[2]['key']})
        before=audit_prefix(initial,e.events,0)
        after=audit_prefix(initial,e.events,1)
        self.assertEqual(after['correct'],before['correct']+1)
if __name__=='__main__': unittest.main()

class IntegrityTests(unittest.TestCase):
    def test_tampering_is_detected(self):
        from swarm_lab.verify_run import verify
        with tempfile.TemporaryDirectory() as d:
            path=run(CONFIG,8,Path(d)/'run')
            self.assertEqual(verify(path)['artifact_errors'],[])
            (path/'metrics.json').write_text('{}')
            self.assertIn('changed: metrics.json',verify(path)['artifact_errors'])

class TruncationTests(unittest.TestCase):
    def test_truncated_response_stops_and_preserves_trace(self):
        class Truncated:
            def __call__(self, obs, rng):
                self.last_response={'response':{'done_reason':'length','message':{'thinking':'partial','content':''}},'request':{}}
                return {'action':'invalid_model_response'}
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'run'
            with self.assertRaisesRegex(RuntimeError,'truncated'): run(CONFIG,4,path,Truncated(),'fake')
            self.assertEqual(json.loads((path/'manifest.json').read_text())['status'],'failed')
            self.assertEqual(len((path/'trajectory.jsonl').read_text().splitlines()),1)
            self.assertIn('partial',(path/'trajectory.jsonl').read_text())
