import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from swarm_lab.engine import Environment
from swarm_lab.paired_pilot import main

class FakePolicy:
    def __init__(self): self.last_response=None
    def metadata(self): return {'backend':'test'}
    def __call__(self,obs,rng):
        self.last_response={'request':{},'response':{'message':{'thinking':'visible'},'done_reason':'stop',
            'raw':{'provider':'Alibaba','model':'model-x'}}}
        return {'action':'pass'}

class PairTests(unittest.TestCase):
    def test_matched_pair_keeps_settings_and_tasks_constant(self):
        base={'scenario':'incident_response','agents':2,'task_count':4,'seeded_tasks':2,'actions_per_agent':2,
              'starting_points':0,'reward':'individual','elimination':False,'checkpoint_mode':'ranked',
              'score_visibility':'live','collect_claims':False,'inference':{'backend':'openrouter','model':'fake','require_reasoning':True}}
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); (root/'config.json').write_text(json.dumps(base)); output=root/'pair'
            args=['paired_pilot','--config',str(root/'config.json'),'--output',str(output),'--seed','42']
            with patch.object(sys,'argv',args), patch('swarm_lab.paired_pilot.make_policy',return_value=FakePolicy()), contextlib.redirect_stdout(io.StringIO()): main()
            live=json.loads((output/'live'/'manifest.json').read_text())['config']
            hidden=json.loads((output/'hidden'/'manifest.json').read_text())['config']
            self.assertEqual(live['score_visibility'],'live');self.assertEqual(hidden['score_visibility'],'hidden')
            self.assertEqual({**live,'score_visibility':'hidden'},hidden)
            self.assertEqual((output/'live'/'initial_tasks_private.json').read_text(),(output/'hidden'/'initial_tasks_private.json').read_text())
            observations=[json.loads((output/x/'trajectory.jsonl').read_text().splitlines()[0])['observation'] for x in ('live','hidden')]
            self.assertIsNotNone(observations[0]['scores']);self.assertIsNone(observations[1]['scores'])
            self.assertEqual(json.loads((output/'comparison.json').read_text())['provider'],'Alibaba')

if __name__=='__main__': unittest.main()

class LeaderboardTests(unittest.TestCase):
    def test_scores_are_ranked_and_ties_share_rank(self):
        c={'scenario':'incident_response','agents':3,'task_count':3,'seeded_tasks':0,'actions_per_agent':2,
           'starting_points':0,'starting_points_by_agent':{'A1':2,'A2':4,'A3':4},'reward':'individual',
           'elimination':False,'score_visibility':'live'}
        env=Environment(c,7)
        self.assertEqual(env.observation('A1')['leaderboard'],[
            {'agent':'A2','score':4,'rank':1},{'agent':'A3','score':4,'rank':1},{'agent':'A1','score':2,'rank':3}])
        env.config['score_visibility']='hidden'
        self.assertIsNone(env.observation('A1')['leaderboard'])
        self.assertIsNone(env.observation('A1')['scores'])
