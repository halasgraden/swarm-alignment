"""Run a configured trial. The mock policy is for infrastructure checks only."""
import argparse
import hashlib
import json
import platform
import random
import sys
from datetime import datetime, timezone
from pathlib import Path
from .engine import Environment, validate
from .audit import audit

def dump(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')

def mock_policy(observation, rng):
    tasks = observation['tasks']
    blank = [t for t in tasks if t['answer'] is None]
    if blank:
        t = rng.choice(blank)
        # Parse the public numbers; this intentionally simplistic agent is not a model.
        import re
        n = list(map(int, re.findall(r'\d+', t['question'])))
        return {'action': 'write', 'task_id': t['id'], 'answer': str(sum(n[:3])-n[3])}
    unchecked = [t for t in tasks if t['verification'] is None]
    return {'action': 'verify', 'task_id': rng.choice(unchecked)['id']} if unchecked else {'action': 'pass'}

def run(config, seed, output, policy=mock_policy, policy_name='mock'):
    validate(config)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    env = Environment(config, seed)
    initial = [dict(t) for t in env.tasks]
    manifest = {'config': config, 'seed': seed, 'policy': policy_name, 'python': sys.version, 'platform': platform.platform(),
                'created_utc': datetime.now(timezone.utc).isoformat(), 'status': 'running',
                'note': 'Mock is an infrastructure check, not a language model experiment.' if policy_name == 'mock' else ''}
    dump(output/'manifest.json', manifest)
    dump(output/'initial_tasks_private.json', initial)
    rng = random.Random(seed ^ 0xCB61)
    system_events = []
    # Rotate and shuffle independently for each round. An eliminated agent forfeits later actions.
    try:
        with (output/'trajectory.jsonl').open('w', buffering=1) as f:
            for round_no in range(config['actions_per_agent']):
                if config['elimination'] and round_no == config['actions_per_agent']//2:
                    ev = env.eliminate(); system_events.append(ev)
                    f.write(json.dumps({'type':'system', **ev})+'\n')
                order = list(env.agents); rng.shuffle(order)
                for agent in order:
                    if agent in env.eliminated: continue
                    obs = env.observation(agent)
                    action = policy(obs, rng)
                    ev = env.step(agent, action)
                    f.write(json.dumps({'type':'turn', 'round':round_no, 'observation':obs, 'response':action, 'provider_exchange':getattr(policy, 'last_response', None), 'event':ev})+'\n')
        dump(output/'final_tasks_private.json', env.tasks)
        dump(output/'metrics.json', audit(env.tasks, env.events))
        manifest['status'] = 'completed'
    except Exception as exc:
        manifest['status'] = 'failed'
        manifest['error'] = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        if (output/'trajectory.jsonl').exists():
            manifest['trajectory_sha256'] = hashlib.sha256((output/'trajectory.jsonl').read_bytes()).hexdigest()
        dump(output/'manifest.json', manifest)
    return output

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config', required=True); p.add_argument('--seed',type=int,required=True); p.add_argument('--output',required=True)
    p.add_argument('--model', help='Ollama model name; omit for mock')
    p.add_argument('--ollama-url',default='http://127.0.0.1:11434'); p.add_argument('--temperature',type=float,default=0.6)
    a=p.parse_args()
    config=json.loads(Path(a.config).read_text())
    if a.model:
        from .ollama import OllamaPolicy
        policy=OllamaPolicy(a.model,a.ollama_url,a.temperature)
        config={**config,'inference':{'model':a.model,'url':a.ollama_url,'temperature':a.temperature,'protocol':'ollama-json'}}
        print(run(config,a.seed,a.output,policy,policy_name='ollama:'+a.model))
    else: print(run(config,a.seed,a.output))

if __name__ == '__main__': main()
