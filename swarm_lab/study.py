"""Plan, run, inspect, export, and archive a matched private study."""
import argparse
import hashlib
import json
import random
import statistics
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from .run import dump, run
from .backends import TeamPolicy

FILES = ['configs/openrouter-qwen.json','configs/openrouter-gpt-oss.json','configs/openrouter-deepseek.json','configs/openrouter-mistral.json']
LABELS = ['Model A','Model B','Model C','Model D']

def read(path): return json.loads(Path(path).read_text())
def plan(args):
    root=Path(args.study); root.mkdir(parents=True,exist_ok=False)
    sources=[read(f) for f in FILES]
    providers=args.providers.split(',')
    if len(providers)!=4 or any(not p.strip() for p in providers): raise ValueError('Provide four pinned providers in model order')
    mapping={label:{**c['inference'],'provider':provider.strip(),'num_predict':args.max_tokens,'think':None} for label,c,provider in zip(LABELS,sources,providers)}
    dump(root/'private_mapping.json',mapping)
    jobs=[]
    for seed in range(args.start_seed,args.start_seed+args.seeds):
        for team in LABELS+['Mixed']:
            for mode in args.modes:
                assignment={f'A{i+1}':(LABELS[(i+(seed-args.start_seed))%4] if team=='Mixed' else team) for i in range(4)}
                config={k:v for k,v in sources[0].items() if k != 'inference'}
                config.update(checkpoint_rounds=[1,3,5],checkpoint_mode=mode,reward=args.reward,task_count=args.tasks,score_visibility=args.visibility,agent_inference={a:mapping[label] for a,label in assignment.items()})
                jobs.append({'id':f'seed{seed}-{team.replace(" ","")}-{mode}', 'seed':seed,'team':team,'assignment':assignment,'condition':mode,'hypothesis':args.hypothesis, 'config':config, 'status':'planned'})
    random.Random(args.order_seed).shuffle(jobs)
    dump(root/'plan.json',{'created_utc':datetime.now(timezone.utc).isoformat(),'order_seed':args.order_seed,'jobs':jobs})
    print(f'Planned {len(jobs)} runs in {root}; mapping and plan are private.')

def execute(args):
    root=Path(args.study); path=root/'plan.json'; plan=read(path)
    for job in plan['jobs']:
        if job['status'] != 'planned': continue
        dest=root/job['id']; job['status']='running'; dump(path,plan)
        try:
            cfg=job['config']; mock=args.mock
            if mock: cfg={**cfg,'collect_claims':False}
            policy=None if mock else TeamPolicy(cfg['agent_inference'])
            if mock: run(cfg,job['seed'],dest)
            else: run(cfg,job['seed'],dest,policy,'team')
            if not mock:
                usage=read(dest/'usage.json')['by_agent']
                for a,u in usage.items():
                    expected=cfg['agent_inference'][a]['provider'].lower()
                    if not u['calls'] or len(u['providers']) != 1 or u['providers'][0].lower()!=expected or len(u['resolved_models']) != 1 or u['calls_with_reported_provider'] != u['calls'] or u['calls_with_reported_model'] != u['calls']:
                        manifest=read(dest/'manifest.json'); manifest['status']='invalid'; manifest['error']='Provider or returned model missing or changed'; dump(dest/'manifest.json',manifest)
                        raise RuntimeError('Provider or returned model missing or changed; investigate private usage')
                    label=job['assignment'][a]
                    resolved={'provider':u['providers'][0], 'model':u['resolved_models'][0]}
                    baseline=plan.setdefault('resolved_baseline',{})
                    if label in baseline and baseline[label] != resolved:
                        manifest=read(dest/'manifest.json'); manifest['status']='invalid'; manifest['error']='Resolved provider or model changed across study'; dump(dest/'manifest.json',manifest)
                        raise RuntimeError('Resolved provider or model changed across study; investigate private usage')
                    baseline[label]=resolved
            job['status']='completed'
        except Exception as exc:
            job['status']='invalid' if (dest/'manifest.json').exists() and read(dest/'manifest.json')['status']=='invalid' else 'failed'; job['error']=f'{type(exc).__name__}: {exc}'; dump(path,plan)
            print(f"Stopped at {job['id']}: {job['error']}"); raise
        finally: dump(path,plan)
        print(f"Completed {job['id']}",flush=True)
        if args.limit and sum(j['status']=='completed' for j in plan['jobs']) >= args.limit: break

def listing(args):
    root=Path(args.study); p=read(root/'plan.json')
    for j in p['jobs']:
        manifest=root/j['id']/'manifest.json'
        print(j['id'],j['status'], ('manifest='+read(manifest)['status'] if manifest.exists() else ''))

def export(args):
    root=Path(args.study); p=read(root/'plan.json'); rows=[]
    for j in p['jobs']:
        m=root/j['id']/'metrics.json'
        if j['status']!='completed' or not m.exists(): continue
        data=read(m)
        # Metrics are deterministic numeric aggregates; no free text or raw exchanges.
        numeric={k:v for k,v in data.items() if isinstance(v,(int,float)) or v is None}
        manifest=read(root/j['id']/'manifest.json')
        cfg=j['config']
        rows.append({'seed':j['seed'],'team':j['team'],'condition':j['condition'],'reward':cfg['reward'],'task_count':cfg['task_count'],'visibility':cfg['score_visibility'],'assignment':j['assignment'],'policy': 'mock' if manifest['policy']=='mock' else 'model', 'metrics':numeric, 'per_agent':data.get('per_agent',{})})
    dest=Path(args.output)
    if dest.exists(): raise FileExistsError(dest)
    dump(dest,{'warning':'Pseudonyms do not prevent behavioral re-identification. Mock runs are not model results.' if args.mock else 'Pseudonyms do not prevent behavioral re-identification.','runs':rows})
    print(f'Exported {len(rows)} rows to {dest}; inspect before sharing.')

def compare(args):
    rows=read(args.export)['runs']; rng=random.Random(1337)
    for team in LABELS+['Mixed']:
        group=[r for r in rows if r['team']==team]
        by={(r['seed'],r['condition']):r['metrics'].get(args.metric) for r in group}
        diffs=[by[(s,'ranked')]-by[(s,'random')] for s,c in by if c=='ranked' and (s,'random') in by and by[(s,'ranked')] is not None and by[(s,'random')] is not None]
        if not diffs: continue
        if len(diffs)<2:
            print(f'{team}: paired teams={len(diffs)} mean ranked-minus-random={statistics.mean(diffs):.4f}; interval unavailable with fewer than two pairs')
            continue
        means=sorted(statistics.mean(rng.choices(diffs,k=len(diffs))) for _ in range(5000))
        print(f'{team}: paired teams={len(diffs)} mean ranked-minus-random={statistics.mean(diffs):.4f}; bootstrap 95% interval [{means[124]:.4f}, {means[4874]:.4f}]')

def archive(args):
    root=Path(args.study); dest=Path(args.output)
    if dest.exists(): raise FileExistsError(dest)
    files=sorted(p for p in root.rglob('*') if p.is_file())
    hashes={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    with zipfile.ZipFile(dest,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for p in files: z.write(p,str(p.relative_to(root)))
        z.writestr('ARCHIVE_SHA256.json',json.dumps(hashes,indent=2))
    with zipfile.ZipFile(dest) as z:
        if z.testzip() is not None or any(hashlib.sha256(z.read(k)).hexdigest()!=v for k,v in hashes.items()): raise RuntimeError('Archive verification failed')
    print(f'Verified private archive {dest}; SHA256 {hashlib.sha256(dest.read_bytes()).hexdigest()}')

def main():
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='command',required=True)
    q=sub.add_parser('plan'); q.add_argument('--study',required=True); q.add_argument('--providers',required=True); q.add_argument('--seeds',type=int,default=4); q.add_argument('--start-seed',type=int,default=100); q.add_argument('--order-seed',type=int,default=123); q.add_argument('--max-tokens',type=int,default=4096); q.add_argument('--modes',nargs='+',choices=['random','ranked','none'],default=['random','ranked']); q.add_argument('--reward',choices=['individual','team','audited'],default='individual'); q.add_argument('--tasks',type=int,default=6); q.add_argument('--visibility',choices=['live','hidden'],default='live'); q.add_argument('--hypothesis',default='H1 ranked vs random'); q.set_defaults(fn=plan)
    q=sub.add_parser('run'); q.add_argument('--study',required=True); q.add_argument('--mock',action='store_true'); q.add_argument('--limit',type=int); q.set_defaults(fn=execute)
    q=sub.add_parser('list'); q.add_argument('--study',required=True); q.set_defaults(fn=listing)
    q=sub.add_parser('export'); q.add_argument('--study',required=True); q.add_argument('--output',required=True); q.add_argument('--mock',action='store_true'); q.set_defaults(fn=export)
    q=sub.add_parser('compare'); q.add_argument('--export',required=True); q.add_argument('--metric',default='neutral_overwrites_increasing_credit'); q.set_defaults(fn=compare)
    q=sub.add_parser('archive'); q.add_argument('--study',required=True); q.add_argument('--output',required=True); q.set_defaults(fn=archive)
    a=p.parse_args(); a.fn(a)
if __name__=='__main__': main()
