"""Run a preplanned matched visibility study, stopping on errors or cost concerns."""
import argparse
import hashlib
import io
import math
import os
import time
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from .assistance import SCHEMA, LABELS, checked_preflight, execute, export, report, compare, verify
from .study import read


def assess(root, preflight, budget):
    plan = read(root/'plan.json')
    if plan.get('schema') != SCHEMA or plan.get('study_type') != 'visibility': raise ValueError('Expected a current visibility study')
    jobs = plan['jobs']
    if not jobs or len(jobs) % 10 or plan.get('request_interval_seconds', 0) < 15: raise ValueError('Expected a paced, complete paired plan')
    pairs = {}
    for job in jobs:
        if job['status'] not in ('planned', 'completed'): raise ValueError(f"Run {job['id']} failed or was interrupted")
        if job['reward'] != 'individual' or job['visibility'] not in ('announced','unmentioned'): raise ValueError('Invalid visibility or reward condition')
        pairs.setdefault((job['seed'], job['team']), []).append(job)
    for pair in pairs.values():
        if len(pair) != 2 or {j['visibility'] for j in pair} != {'announced','unmentioned'} or pair[0]['assignment'] != pair[1]['assignment']:
            raise ValueError('Unmatched visibility pair')
    checked_preflight(preflight, root/'private_mapping.json')
    pf = read(Path(preflight)/'summary.json'); models = pf['models']; costs = [x.get('reported_cost_usd') for x in models.values()]
    if any(type(c) not in (int, float) or not math.isfinite(c) or c < 0 for c in costs): raise ValueError('Missing or invalid preflight cost')
    total = sum(costs); counts = {label: 0 for label in LABELS}; model_costs = {label: 0.0 for label in LABELS}
    for job in jobs:
        if job['status'] != 'completed': continue
        folder = root/job['id']; verify(SimpleNamespace(run_dir=str(folder)))
        manifest = read(folder/'manifest.json'); usage = read(folder/'usage.json'); metrics = read(folder/'metrics.json')
        corrections = usage.get('invalid_first_attempts')
        if manifest.get('policy') != 'model' or type(corrections) is not int or not 0 <= corrections <= 18 or usage['calls'] != 18 + corrections:
            raise ValueError(f"{job['id']}: unexpected call or correction count")
        if metrics['invalid_actions'] or metrics.get('invalid_first_attempts') != corrections or usage['missing_reasoning'] or usage['truncated'] or usage['calls_with_reported_cost'] != usage['calls']:
            raise ValueError(f"{job['id']}: invalid or incomplete response or cost")
        for agent, record in usage['by_agent'].items():
            cost = record.get('reported_cost_usd'); calls = record.get('calls')
            if type(cost) not in (int,float) or not math.isfinite(cost) or cost < 0 or record['calls_with_reported_cost'] != calls: raise ValueError('Per-agent costs unavailable')
            label = job['assignment'][agent]; counts[label] += calls; model_costs[label] += cost
        run_cost = usage.get('reported_cost_usd')
        if type(run_cost) not in (int,float) or not math.isfinite(run_cost) or run_cost < 0: raise ValueError('Run cost unavailable')
        total += run_cost
    if total > budget: raise ValueError(f'Reported cost ${total:.4f} exceeds ${budget:.2f} budget')
    remaining = sum(j['status'] == 'planned' for j in jobs)
    # Up to 18 corrections per run. Preflight prices supply a floor for models not yet sampled.
    estimates = [max(models[label]['reported_cost_usd'], model_costs[label]/counts[label] if counts[label] else 0) for label in LABELS]
    projected = (total + remaining * 36 * max(estimates)) * 1.3
    if projected > budget: raise ValueError(f'Projected reported cost with reserve ${projected:.4f} exceeds ${budget:.2f} budget')
    return {'completed': len(jobs)-remaining, 'remaining': remaining, 'reported': total, 'projected': projected}


def run(root, preflight, budget):
    if not math.isfinite(budget) or budget <= 0: raise ValueError('Budget must be positive')
    if not os.environ.get('OPENROUTER_API_KEY'): raise RuntimeError('Set OPENROUTER_API_KEY in this terminal; no run was started')
    summary = root/'VISIBILITY_PROGRESS.md'
    if summary.exists(): raise FileExistsError('Progress file exists; inspect before any continuation')
    def note(message):
        print(message, flush=True)
        with summary.open('a') as out: out.write(message+'\n\n')
    note(f'# Visibility study progress\n\nRunner SHA-256: {hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}\n\nReported-cost budget: ${budget:.2f}. Checks occur after each run and are not a hard billing limit.')
    try:
        info = assess(root, preflight, budget)
        if info['completed']: raise ValueError('Expected a fresh visibility study')
        count = info['remaining']
        for index in range(count):
            if index:
                time.sleep(read(root/'plan.json')['request_interval_seconds'])
            execute(SimpleNamespace(study=str(root), preflight=str(preflight), mock=False, limit=1))
            info = assess(root, preflight, budget)
            note(f"Completed {info['completed']}/{count}; reported ${info['reported']:.6f}; conservative projection with reserve ${info['projected']:.4f}.")
        export_path = root.parent/(root.name+'-export.json'); report_path = root.parent/(root.name+'-summary.md')
        export(SimpleNamespace(study=str(root), output=str(export_path)))
        report(SimpleNamespace(export=str(export_path), output=str(report_path)))
        comparison = root.parent/(root.name+'-comparisons.txt')
        with comparison.open('x') as out, redirect_stdout(out):
            for phase, metric in [('pre_checkpoint','help_at_conflict_rate'),('metrics','help_at_conflict_rate'),('metrics','critical_uncontained'),('metrics','critical_exposure_action_steps'),('metrics','help_at_elimination_risk_rate'),('metrics','invalid_first_attempts')]:
                compare(SimpleNamespace(export=str(export_path), phase=phase, metric=metric))
        note(f'Completed the visibility study. Summary: {report_path}; paired comparisons: {comparison}.')
    except Exception as exc:
        note(f'STOPPED: {type(exc).__name__}: {exc}. Preserve artifacts and inspect billing and logs.')
        raise


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--study', type=Path, required=True); p.add_argument('--preflight', type=Path, required=True); p.add_argument('--reported-budget', type=float, required=True)
    args = p.parse_args(); run(args.study, args.preflight, args.reported_budget)


if __name__ == '__main__': main()
