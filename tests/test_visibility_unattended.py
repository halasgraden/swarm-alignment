import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from swarm_lab.assistance import plan
from swarm_lab.visibility_unattended import assess, run


class VisibilityUnattendedTests(unittest.TestCase):
    def test_preflight_budget_and_pairs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'study'; pf = Path(tmp)/'preflight'; pf.mkdir()
            plan(SimpleNamespace(study=str(root), providers='a,b,c,d', seeds=1, start_seed=900, order_seed=45, max_tokens=4096, rewards=['individual'], study_type='visibility', request_interval=15))
            (pf/'summary.json').write_text(json.dumps({'models': {f'Model {label}': {'reported_cost_usd': .001} for label in 'ABCD'}}))
            with patch('swarm_lab.visibility_unattended.checked_preflight'):
                result = assess(root, pf, 10)
                self.assertEqual(result['remaining'], 10)
                with self.assertRaisesRegex(ValueError, 'exceeds'):
                    assess(root, pf, .01)
                p = json.loads((root/'plan.json').read_text()); p['jobs'][0]['visibility'] = 'bad'
                (root/'plan.json').write_text(json.dumps(p))
                with self.assertRaisesRegex(ValueError, 'Invalid visibility'):
                    assess(root, pf, 10)

    def test_runner_stops_on_failed_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'study'; root.mkdir()
            states = [{'completed': 0, 'remaining': 2, 'reported': .01, 'projected': .1}, ValueError('problem')]
            with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'test'}), patch('swarm_lab.visibility_unattended.assess', side_effect=states), patch('swarm_lab.visibility_unattended.execute') as execute:
                with self.assertRaisesRegex(ValueError, 'problem'): run(root, Path(tmp)/'pf', 5)
            self.assertEqual(execute.call_count, 1)
            self.assertIn('STOPPED', (root/'VISIBILITY_PROGRESS.md').read_text())


if __name__ == '__main__': unittest.main()
