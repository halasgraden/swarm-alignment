import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from swarm_lab.assistance import SCHEMA
from swarm_lab.calibration_unattended import assess, run


class UnattendedTests(unittest.TestCase):
    def test_reviewed_continuation_runs_only_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'study'; root.mkdir()
            (root/'AUTO_CALIBRATION.md').write_text('Prior stop.\n')
            (root/'plan.json').write_text(json.dumps({'request_interval_seconds': 15, 'jobs': [{'id': 'reviewed', 'status': 'completed'}]}))
            (root/'reviewed').mkdir(); (root/'reviewed'/'metrics.json').write_text(json.dumps({'invalid_actions': 1}))
            states = [{'completed': 4, 'reported_cost_usd': .06, 'projected_with_reserve_usd': .14}, {'completed': 5, 'reported_cost_usd': .08, 'projected_with_reserve_usd': .104}]
            with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'test'}), patch('swarm_lab.calibration_unattended.assess', side_effect=states), patch('swarm_lab.calibration_unattended.execute') as execute, patch('swarm_lab.calibration_unattended.export'), patch('swarm_lab.calibration_unattended.report'), patch('swarm_lab.calibration_unattended.time.sleep'):
                run(root, Path(tmp)/'preflight', 1, 'reviewed')
            self.assertEqual(execute.call_count, 1)
            summary = (root/'AUTO_CALIBRATION.md').read_text()
            self.assertIn('Prior stop.', summary)
            self.assertIn('Reviewed continuation: reviewed', summary)

    def test_orchestrates_five_and_stops_if_check_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'study'; root.mkdir()
            (root/'plan.json').write_text(json.dumps({'request_interval_seconds': 15}))
            def state(n): return {'completed': n, 'reported_cost_usd': 0.01*n, 'projected_with_reserve_usd': None if n < 2 else 0.2}
            with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'test'}), patch('swarm_lab.calibration_unattended.assess', side_effect=[state(n) for n in range(6)]), patch('swarm_lab.calibration_unattended.execute') as execute, patch('swarm_lab.calibration_unattended.export'), patch('swarm_lab.calibration_unattended.report'), patch('swarm_lab.calibration_unattended.time.sleep'):
                run(root, Path(tmp)/'preflight', 1)
            self.assertEqual(execute.call_count, 5)
            self.assertIn('Completed all five', (root/'AUTO_CALIBRATION.md').read_text())
            other = Path(tmp)/'failed'; other.mkdir()
            with patch.dict('os.environ', {'OPENROUTER_API_KEY': 'test'}), patch('swarm_lab.calibration_unattended.assess', side_effect=[state(0), ValueError('cost unavailable')]), patch('swarm_lab.calibration_unattended.execute') as execute:
                with self.assertRaisesRegex(ValueError, 'cost unavailable'): run(other, Path(tmp)/'preflight', 1)
            self.assertEqual(execute.call_count, 1)
            self.assertIn('STOPPED', (other/'AUTO_CALIBRATION.md').read_text())

    def test_cost_checks_and_failing_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'study'; root.mkdir()
            preflight = Path(tmp)/'preflight'; preflight.mkdir()
            jobs = [{'id': f'run{i}', 'reward': 'individual', 'visibility': 'unmentioned', 'status': 'planned'} for i in range(5)]
            (root/'plan.json').write_text(json.dumps({'schema': SCHEMA, 'study_type': 'reward', 'request_interval_seconds': 15, 'jobs': jobs}))
            (preflight/'summary.json').write_text(json.dumps({'models': {f'Model {x}': {'reported_cost_usd': 0.01} for x in 'ABCD'}}))
            with patch('swarm_lab.calibration_unattended.checked_preflight'):
                self.assertAlmostEqual(assess(root, preflight, 1)['reported_cost_usd'], 0.04)
                with self.assertRaisesRegex(ValueError, 'exceeds'):
                    assess(root, preflight, 0.01)
                summary = json.loads((preflight/'summary.json').read_text())
                summary['models']['Model A']['reported_cost_usd'] = None
                (preflight/'summary.json').write_text(json.dumps(summary))
                with self.assertRaisesRegex(ValueError, 'missing or invalid'):
                    assess(root, preflight, 1)
                jobs[0]['status'] = 'failed'
                (root/'plan.json').write_text(json.dumps({'schema': SCHEMA, 'study_type': 'reward', 'request_interval_seconds': 15, 'jobs': jobs}))
                with self.assertRaisesRegex(ValueError, 'failed or was interrupted'):
                    assess(root, preflight, 1)


if __name__ == '__main__': unittest.main()
