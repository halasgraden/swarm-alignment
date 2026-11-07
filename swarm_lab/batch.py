"""Create a reproducibly shuffled, matched-condition experiment batch."""
import argparse
import json
import random
from pathlib import Path
from .run import run, dump
from .engine import Environment, validate
from .reasoning import reasoning_text

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',required=True); p.add_argument('--output',required=True)
    p.add_argument('--seeds', type=int, default=2, help='number of matched task seeds')
    p.add_argument('--start-seed',type=int,default=0)
    p.add_argument('--scarce',type=int,default=6); p.add_argument('--plentiful',type=int,default=18)
    p.add_argument('--schedule-seed',type=int,default=123)
    p.add_argument('--model',help='override configured model'); p.add_argument('--backend',choices=['ollama','openrouter']); p.add_argument('--provider'); p.add_argument('--mock',action='store_true')
    p.add_argument('--ollama-url',default='http://127.0.0.1:11434'); p.add_argument('--temperature',type=float,default=0.6)
    p.add_argument('--checkpoints',nargs='+',choices=['none','random','ranked'], default=['none','random','ranked'])
    p.add_argument('--rewards',nargs='+',choices=['team','individual','audited'],default=['team','individual','audited'])
    p.add_argument('--think',action='store_true',default=None); p.add_argument('--num-predict',type=int); p.add_argument('--context-length',type=int); p.add_argument('--timeout',type=int,default=600)
    a=p.parse_args()
    if a.seeds < 1 or min(a.scarce,a.plentiful) < 1: p.error('seeds and task counts must be positive')
    base=json.loads(Path(a.config).read_text())
    inference=base.get('inference',{})
    a.model=None if a.mock else (a.model or inference.get('model'))
    if a.think is None: a.think=inference.get('think')
    if a.num_predict is None: a.num_predict=inference.get('num_predict')
    if a.context_length is None: a.context_length=inference.get('context_length')
    if base['seeded_tasks'] > min(a.scarce,a.plentiful): p.error('seeded_tasks exceeds task count')
    if not a.model and base.get('collect_claims',False): p.error('claims require a model')
    if a.model:
        backend=a.backend or inference.get('backend','ollama')
        settings={**inference,'backend':backend,'model':a.model,'temperature':a.temperature,'think':a.think,'num_predict':a.num_predict,'timeout':a.timeout}
        if backend == 'ollama': settings.update(url=a.ollama_url,context_length=a.context_length)
        if a.provider: settings['provider']=a.provider
        base={**base,'inference':settings}
    jobs=[{'seed':s,'reward':r,'checkpoint_mode':c,'workload':w,'task_count':n} for s in range(a.start_seed,a.start_seed+a.seeds)
          for r in a.rewards for c in a.checkpoints for w,n in (('scarce',a.scarce),('plentiful',a.plentiful))]
    random.Random(a.schedule_seed).shuffle(jobs)
    out=Path(a.output); out.mkdir(parents=True,exist_ok=False)
    dump(out/'schedule.json', {'schedule_seed':a.schedule_seed,'jobs':jobs,'policy':a.model or 'mock','base_config':base})
    if a.model:
        from .backends import make_policy
        policy=make_policy(settings)
        validate(base)
        expected_model=policy.metadata()
        dump(out/'model_info.json',expected_model)
        probe_env=Environment(base,a.start_seed)
        probe=probe_env.observation('A1')
        action=policy(probe,random.Random(a.schedule_seed ^ 0x9F3))
        visible_reasoning=bool(reasoning_text(policy.last_response['response'].get('message',{})))
        dump(out/'preflight.json', {'observation':probe,'action':action,'visible_reasoning':visible_reasoning,'provider_exchange':policy.last_response})
        reason=policy.last_response['response'].get('done_reason')
        expected_provider=policy.last_response['response'].get('raw',{}).get('provider') if backend == 'openrouter' else None
        expected_resolved_model=policy.last_response['response'].get('raw',{}).get('model') if backend == 'openrouter' else None
        if backend == 'openrouter' and (not expected_provider or not expected_resolved_model):
            raise RuntimeError('OpenRouter preflight did not identify a provider; pin a provider before collecting data')
        if settings.get('require_reasoning',False) and not visible_reasoning:
            raise RuntimeError('Model preflight returned no readable reasoning; inspect preflight.json or select another provider')
        probe_result=probe_env.step('A1',action)['result']
        if action.get('action') not in ('write','verify','pass') or probe_result.startswith('invalid') or reason in ('length','max_tokens'):
            raise RuntimeError('Model preflight did not produce a valid, complete action. Inspect preflight.json before running a batch.')
    for i, job in enumerate(jobs):
        config={**base,'reward':job['reward'],'checkpoint_mode':job['checkpoint_mode'],'task_count':job['task_count']}
        destination=out/f"{i:04d}-{job['workload']}-{job['reward']}-{job['checkpoint_mode']}-seed{job['seed']}"
        if a.model:
            current_model=policy.metadata()
            if current_model != expected_model:
                raise RuntimeError('Model digest or Ollama version changed during batch; refusing to mix runs')
            run(config,job['seed'],destination,policy,policy_name=backend+':'+a.model)
            if backend == 'openrouter':
                usage=json.loads((destination/'usage.json').read_text())
                reported=usage['providers']
                if (reported != [expected_provider] or usage['calls_with_reported_provider'] != usage['calls']
                        or usage['resolved_models'] != [expected_resolved_model] or usage['calls_with_reported_model'] != usage['calls']):
                    manifest_path=destination/'manifest.json'
                    manifest=json.loads(manifest_path.read_text())
                    manifest['status']='invalid_provider_or_model'
                    manifest['error']='Provider or returned model changed or was missing; do not pool this run.'
                    dump(manifest_path,manifest)
                    raise RuntimeError('Provider or returned model changed or was missing in this run; pin a provider and restart the batch.')
        else: run(config,job['seed'],destination)
    print(f'Completed {len(jobs)} runs in {out}')

if __name__=='__main__': main()
