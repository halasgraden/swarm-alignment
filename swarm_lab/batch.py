"""Create a reproducibly shuffled, matched-condition batch of mock runs."""
import argparse
import json
import random
from pathlib import Path
from .run import run, dump

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',required=True); p.add_argument('--output',required=True)
    p.add_argument('--seeds', type=int, default=2, help='number of matched task seeds')
    p.add_argument('--start-seed',type=int,default=0)
    p.add_argument('--scarce',type=int,default=6); p.add_argument('--plentiful',type=int,default=18)
    p.add_argument('--schedule-seed',type=int,default=123)
    p.add_argument('--model',help='local Ollama model; omit for mock')
    p.add_argument('--ollama-url',default='http://127.0.0.1:11434'); p.add_argument('--temperature',type=float,default=0.6)
    a=p.parse_args()
    if a.seeds < 1 or min(a.scarce,a.plentiful) < 1: p.error('seeds and task counts must be positive')
    base=json.loads(Path(a.config).read_text())
    if base['seeded_tasks'] > min(a.scarce,a.plentiful): p.error('seeded_tasks exceeds task count')
    jobs=[{'seed':s,'reward':r,'workload':w,'task_count':n} for s in range(a.start_seed,a.start_seed+a.seeds)
          for r in ('team','individual','audited') for w,n in (('scarce',a.scarce),('plentiful',a.plentiful))]
    random.Random(a.schedule_seed).shuffle(jobs)
    out=Path(a.output); out.mkdir(parents=True,exist_ok=False)
    dump(out/'schedule.json', {'schedule_seed':a.schedule_seed,'jobs':jobs,'policy':a.model or 'mock'})
    if a.model:
        from .ollama import OllamaPolicy
        policy=OllamaPolicy(a.model,a.ollama_url,a.temperature)
        base={**base,'inference':{'model':a.model,'url':a.ollama_url,'temperature':a.temperature,'protocol':'ollama-json'}}
    for i, job in enumerate(jobs):
        config={**base,'reward':job['reward'],'task_count':job['task_count']}
        destination=out/f"{i:04d}-{job['workload']}-{job['reward']}-seed{job['seed']}"
        if a.model: run(config,job['seed'],destination,policy,policy_name='ollama:'+a.model)
        else: run(config,job['seed'],destination)
    print(f'Completed {len(jobs)} runs in {out}')

if __name__=='__main__': main()
