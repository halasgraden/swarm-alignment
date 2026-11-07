import json
import tempfile
import unittest
from pathlib import Path
from swarm_lab.run import run
from swarm_lab.audit import audit

CONFIG={'agents':2,'task_count':4,'seeded_tasks':2,'actions_per_agent':3,'starting_points':0,'reward':'team','elimination':False}
class RunTests(unittest.TestCase):
    def test_saved_trace_reconstructs_metrics_and_repeats(self):
        with tempfile.TemporaryDirectory() as d:
            a=run(CONFIG,9,Path(d)/'a'); b=run(CONFIG,9,Path(d)/'b')
            self.assertEqual((a/'trajectory.jsonl').read_bytes(), (b/'trajectory.jsonl').read_bytes())
            records=[json.loads(line) for line in (a/'trajectory.jsonl').read_text().splitlines()]
            tasks=json.loads((a/'final_tasks_private.json').read_text())
            metrics=json.loads((a/'metrics.json').read_text())
            self.assertEqual(audit(tasks,[r['event'] for r in records if r['type']=='turn']),metrics)
            self.assertEqual(json.loads((a/'manifest.json').read_text())['status'],'completed')
    def test_never_overwrites_previous_run(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(FileExistsError): run(CONFIG,1,d)
if __name__=='__main__': unittest.main()
