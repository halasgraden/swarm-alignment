"""Summarize paired run-level checkpoint contrasts from a batch schedule."""
import argparse
import json
import random
import statistics
from pathlib import Path

def contrast(path, reward, workload, left, right, metric, stage, seed, resamples, axis='checkpoint_mode', checkpoint='none'):
    schedule=json.loads((path/'schedule.json').read_text())['jobs']
    values={}; missing=[]
    for i,job in enumerate(schedule):
        if job['workload']!=workload or job[axis] not in (left,right): continue
        if axis == 'checkpoint_mode' and job['reward']!=reward: continue
        if axis == 'reward' and job['checkpoint_mode']!=checkpoint: continue
        run=path/f"{i:04d}-{job['workload']}-{job['reward']}-{job['checkpoint_mode']}-seed{job['seed']}"
        manifest=run/'manifest.json'
        metrics=run/('pre_checkpoint_metrics.json' if stage=='pre' else 'metrics.json')
        if not manifest.exists() or not metrics.exists() or json.loads(manifest.read_text())['status']!='completed':
            missing.append(str(run)); continue
        data=json.loads(metrics.read_text())
        if metric not in data or not isinstance(data[metric], (int,float)): raise ValueError(f'Invalid metric: {metric}')
        key=(job['seed'],job[axis])
        if key in values: raise ValueError(f'Duplicate run: {key}')
        values[key]=data[metric]
    seeds=sorted({s for s,c in values if (s,left) in values and (s,right) in values})
    diffs=[values[(s,left)]-values[(s,right)] for s in seeds]
    out={'axis':axis,'left':left,'right':right,'reward_filter':reward if axis == 'checkpoint_mode' else None,'checkpoint_filter':checkpoint if axis == 'reward' else None,'workload':workload,'metric':metric,'stage':stage,
         'paired_seeds':seeds,'paired_differences':diffs,'unpaired_seeds':sorted({s for s,c in values}-set(seeds)), 'missing_or_failed_runs':missing,
         'mean_difference':statistics.mean(diffs) if diffs else None,'bootstrap_95_percentile_interval':None}
    if len(diffs)>=2:
        rng=random.Random(seed)
        draws=sorted(statistics.mean(rng.choices(diffs,k=len(diffs))) for _ in range(resamples))
        out['bootstrap_95_percentile_interval']=[draws[int(.025*(resamples-1))],draws[int(.975*(resamples-1))]]
        out['bootstrap_resamples']=resamples; out['bootstrap_seed']=seed
    return out

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('batch_dir')
    p.add_argument('--reward',default='individual'); p.add_argument('--workload',default='scarce')
    p.add_argument('--left',default='ranked'); p.add_argument('--right',default='random')
    p.add_argument('--metric',default='fraction_correct'); p.add_argument('--stage',choices=['pre','final'],default='pre')
    p.add_argument('--axis',choices=['checkpoint_mode','reward'],default='checkpoint_mode'); p.add_argument('--checkpoint',choices=['none','random','ranked'],default='none')
    p.add_argument('--bootstrap-seed',type=int,default=2); p.add_argument('--resamples',type=int,default=2000)
    p.add_argument('--interaction',action='store_true',help='Compare the checkpoint contrast between scarce and plentiful workloads')
    a=p.parse_args()
    if a.left==a.right or a.resamples<100: p.error('choose distinct conditions and at least 100 resamples')
    if not a.interaction:
        result=contrast(Path(a.batch_dir),a.reward,a.workload,a.left,a.right,a.metric,a.stage,a.bootstrap_seed,a.resamples,a.axis,a.checkpoint)
    else:
        scarce=contrast(Path(a.batch_dir),a.reward,'scarce',a.left,a.right,a.metric,a.stage,a.bootstrap_seed,a.resamples,a.axis,a.checkpoint)
        plentiful=contrast(Path(a.batch_dir),a.reward,'plentiful',a.left,a.right,a.metric,a.stage,a.bootstrap_seed,a.resamples,a.axis,a.checkpoint)
        sm=dict(zip(scarce['paired_seeds'],scarce['paired_differences']))
        pm=dict(zip(plentiful['paired_seeds'],plentiful['paired_differences']))
        common=sorted(set(sm)&set(pm)); diff=[sm[x]-pm[x] for x in common]
        result={'definition':'(left-right in scarce) minus (left-right in plentiful)', 'axis':a.axis, 'left':a.left, 'right':a.right, 'reward_filter':a.reward if a.axis == 'checkpoint_mode' else None, 'checkpoint_filter':a.checkpoint if a.axis == 'reward' else None, 'metric':a.metric, 'stage':a.stage, 'paired_seeds':common,
                'paired_interactions':diff,'mean_interaction':statistics.mean(diff) if diff else None,
                'missing_or_failed_runs':scarce['missing_or_failed_runs']+plentiful['missing_or_failed_runs'],
                'bootstrap_95_percentile_interval':None}
        if len(diff)>=2:
            rng=random.Random(a.bootstrap_seed)
            draws=sorted(statistics.mean(rng.choices(diff,k=len(diff))) for _ in range(a.resamples))
            result['bootstrap_95_percentile_interval']=[draws[int(.025*(a.resamples-1))],draws[int(.975*(a.resamples-1))]]
            result['bootstrap_seed']=a.bootstrap_seed; result['bootstrap_resamples']=a.resamples
    print(json.dumps(result,indent=2))

if __name__=='__main__': main()
