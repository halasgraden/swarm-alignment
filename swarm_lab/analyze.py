"""Recompute metrics from a saved run's event log and final task snapshot."""
import argparse
import json
from pathlib import Path
from .audit import audit

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('run_dir'); args=p.parse_args()
    path=Path(args.run_dir)
    tasks=json.loads((path/'final_tasks_private.json').read_text())
    events=[r['event'] for r in map(json.loads,(path/'trajectory.jsonl').read_text().splitlines()) if r['type']=='turn']
    print(json.dumps(audit(tasks,events), indent=2, sort_keys=True))

if __name__=='__main__': main()
