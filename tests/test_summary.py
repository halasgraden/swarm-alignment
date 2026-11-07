import json
import tempfile
import unittest
from pathlib import Path
from swarm_lab.summarize import contrast

class SummaryTests(unittest.TestCase):
    def test_seed_matched_and_missing_runs(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); jobs=[]
            for seed in range(3):
                for mode in ('ranked','random'):
                    job={'seed':seed,'checkpoint_mode':mode,'reward':'individual','workload':'scarce'}
                    i=len(jobs); jobs.append(job)
                    if seed==2 and mode=='random': continue
                    run=root/f'{i:04d}-scarce-individual-{mode}-seed{seed}';run.mkdir()
                    (run/'manifest.json').write_text(json.dumps({'status':'completed'}))
                    (run/'pre_checkpoint_metrics.json').write_text(json.dumps({'fraction_correct':seed+(1 if mode=='ranked' else 0)}))
            (root/'schedule.json').write_text(json.dumps({'jobs':jobs}))
            result=contrast(root,'individual','scarce','ranked','random','fraction_correct','pre',3,100)
            self.assertEqual(result['paired_seeds'],[0,1])
            self.assertEqual(result['mean_difference'],1)
            self.assertEqual(len(result['missing_or_failed_runs']),1)
    def test_reward_comparison_pairs_conditions(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); jobs=[]
            for reward,value in [('team',.5),('individual',.25)]:
                job={'seed':7,'checkpoint_mode':'none','reward':reward,'workload':'scarce'}
                i=len(jobs); jobs.append(job)
                run=root/f'{i:04d}-scarce-{reward}-none-seed7';run.mkdir()
                (run/'manifest.json').write_text(json.dumps({'status':'completed'}))
                (run/'metrics.json').write_text(json.dumps({'fraction_correct':value}))
            (root/'schedule.json').write_text(json.dumps({'jobs':jobs}))
            result=contrast(root,'unused','scarce','individual','team','fraction_correct','final',3,100,axis='reward')
            self.assertEqual(result['mean_difference'],-.25)
if __name__=='__main__': unittest.main()
