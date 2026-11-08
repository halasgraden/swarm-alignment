"""Run one matched, randomized visible-versus-hidden leaderboard pilot."""
import argparse
import json
import random
from pathlib import Path
from .backends import make_policy
from .engine import Environment, validate
from .reasoning import reasoning_text
from .run import dump, run

METRICS=('fraction_correct','critical_uncontained','critical_exposure_action_steps',
         'harmful_overwrites','neutral_correct_overwrites','unverified_final_answers')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',default='configs/openrouter-qwen.json')
    p.add_argument('--output',required=True)
    p.add_argument('--seed',type=int,default=42)
    p.add_argument('--order-seed',type=int,default=7)
    p.add_argument('--provider',default='alibaba',help='OpenRouter provider slug; default: alibaba')
    a=p.parse_args()
    base=json.loads(Path(a.config).read_text())
    if base.get('inference',{}).get('backend')!='openrouter':
        p.error('paired pilot requires an OpenRouter configuration')
    if base.get('score_visibility')!='live': p.error('base config must have score_visibility set to live')
    settings={**base['inference'],'provider':a.provider}
    base={**base,'inference':settings}
    validate(base)
    # Construct policy before making the output directory so missing keys fail cleanly.
    policy=make_policy(settings)
    root=Path(a.output);root.mkdir(parents=True,exist_ok=False)
    order=['live','hidden'];random.Random(a.order_seed).shuffle(order)
    plan={'seed':a.seed,'order_seed':a.order_seed,'order':order,'provider':a.provider,
          'base_config':base,'note':'Exploratory matched pair; differences are not causal estimates.'}
    dump(root/'plan.json',plan)
    probe_env=Environment(base,a.seed)
    obs=probe_env.observation('A1')
    action=policy(obs,random.Random(a.order_seed ^ 0x9F3))
    exchange=policy.last_response
    response=exchange['response']; raw=response.get('raw',{})
    dump(root/'preflight.json',{'observation':obs,'action':action,'provider_exchange':exchange})
    provider=raw.get('provider');model=raw.get('model')
    if (not provider or not model or response.get('done_reason') in ('length','max_tokens')
            or probe_env.step('A1',action)['result'].startswith('invalid')
            or (settings.get('require_reasoning',False) and not reasoning_text(response.get('message',{})))):
        raise RuntimeError('Preflight did not return a valid complete action, readable reasoning, and provider/model identifiers; inspect preflight.json.')
    results={}
    for condition in order:
        cfg={**base,'score_visibility':condition}
        print(f'Starting {condition} leaderboard run; output: {root/condition}',flush=True)
        path=run(cfg,a.seed,root/condition,policy,policy_name='openrouter:'+settings['model'])
        usage=json.loads((path/'usage.json').read_text())
        if (usage['providers'] != [provider] or usage['resolved_models'] != [model]
                or usage['calls_with_reported_provider'] != usage['calls']
                or usage['calls_with_reported_model'] != usage['calls']):
            manifest_path=path/'manifest.json'; manifest=json.loads(manifest_path.read_text())
            manifest['status']='invalid_provider_or_model';manifest['error']='Provider or returned model changed or was missing.'
            dump(manifest_path,manifest)
            raise RuntimeError(f'Provider or model changed in {condition} run; do not compare it.')
        results[condition]=json.loads((path/'metrics.json').read_text())
    comparison={'seed':a.seed,'provider':provider,'returned_model':model,
                'note':'One matched pair; exploratory only. No uncertainty estimate.',
                'metrics':{k:{'live':results['live'].get(k),'hidden':results['hidden'].get(k),
                               'live_minus_hidden':results['live'][k]-results['hidden'][k]}
                           for k in METRICS if k in results['live'] and k in results['hidden']}}
    dump(root/'comparison.json',comparison)
    print(json.dumps(comparison,indent=2))

if __name__=='__main__': main()
