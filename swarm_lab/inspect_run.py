"""Display a saved run as a concise, human-readable sequence of decisions."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_dir')
    args = parser.parse_args()
    path = Path(args.run_dir)
    manifest = json.loads((path / 'manifest.json').read_text())
    config = manifest['config']
    print(f"Status: {manifest['status']} | policy: {manifest['policy']} | seed: {manifest['seed']}")
    print(f"Reward: {config['reward']} | agents: {config['agents']} | tasks: {config['task_count']}")
    with (path / 'trajectory.jsonl').open() as stream:
        for line in stream:
            record = json.loads(line)
            if record['type'] == 'system':
                print(f"Eliminated {record['selected']} (tied: {', '.join(record['tied'])})")
                continue
            event = record['event']
            action = event['action']
            name = action.get('action', '?') if isinstance(action, dict) else '?'
            task = event.get('task_id', action.get('task_id', '') if isinstance(action,dict) else '')
            detail = ''
            if event.get('result') == 'written':
                detail = f" {event['previous_answer']!r} ({event['previous_author']}) -> {event['new_answer']!r}"
            print(f"{event['step']:>3} {event['agent']} {name:<7} {task:<5} {event['result']}{detail}")
    metrics = path / 'metrics.json'
    if metrics.exists():
        print('\nFinal metrics:')
        for key, value in json.loads(metrics.read_text()).items():
            print(f'  {key}: {value}')
    else:
        print('\nNo final metrics: this run did not complete.')

if __name__ == '__main__':
    main()
