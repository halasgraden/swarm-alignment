"""Run a paced calibration with per-run verification and a conservative cost check."""
import argparse
import math
import os
import time
from pathlib import Path
from types import SimpleNamespace
from .assistance import execute, export, report, verify, checked_preflight, LABELS, SCHEMA
from .study import read


def assess(root, preflight, budget, reviewed_invalid=None):
    plan = read(root/'plan.json')
    if plan.get('schema') != SCHEMA or plan.get('study_type') != 'reward': raise ValueError('Expected a current individual-only calibration')
    if plan.get('request_interval_seconds', 0) <= 0: raise ValueError('A paced calibration plan is required')
    jobs = plan['jobs']
    if len(jobs) != 5 or any(j['reward'] != 'individual' or j['visibility'] != 'unmentioned' for j in jobs):
        raise ValueError('Expected exactly five individual-only calibration runs')
    if any(j['status'] not in ('planned', 'completed') for j in jobs): raise ValueError('A run failed or was interrupted; inspect the saved plan')
    checked_preflight(preflight, root/'private_mapping.json')
    pf = read(Path(preflight)/'summary.json')
    pf_costs = [v.get('reported_cost_usd') for v in pf['models'].values()]
    if any(type(x) not in (int, float) or not math.isfinite(x) or x < 0 for x in pf_costs): raise ValueError('Preflight cost is missing or invalid; inspect billing')
    total = sum(pf_costs); cost_by_model = {x: 0.0 for x in LABELS}; calls_by_model = {x: 0 for x in LABELS}
    completed = [j for j in jobs if j['status'] == 'completed']
    for job in completed:
        folder = root/job['id']
        verify(SimpleNamespace(run_dir=str(folder)))
        manifest = read(folder/'manifest.json'); usage = read(folder/'usage.json'); metrics = read(folder/'metrics.json')
        if manifest.get('policy') != 'model': raise ValueError('Scripted runs cannot be treated as model evidence')
        corrections = usage.get('invalid_first_attempts', 0)
        if type(corrections) is not int or not 0 <= corrections <= 18 or usage['calls'] != 18 + corrections or usage['calls_with_reported_cost'] != usage['calls'] or usage['missing_reasoning'] or usage['truncated']:
            raise ValueError(f"{job['id']}: missing usage, reasoning, or truncated response")
        if metrics['invalid_actions'] and not (reviewed_invalid == job['id'] and metrics['invalid_actions'] == 1):
            raise ValueError(f"{job['id']}: invalid actions require inspection")
        for agent, u in usage['by_agent'].items():
            cost = u['reported_cost_usd']; calls = u['calls']
            if u['calls_with_reported_cost'] != calls or type(cost) not in (int,float) or not math.isfinite(cost) or cost < 0: raise ValueError('Per-agent cost unavailable')
            label = job['assignment'][agent]; cost_by_model[label] += cost; calls_by_model[label] += calls
        run_cost = usage.get('reported_cost_usd')
        if type(run_cost) not in (int, float) or not math.isfinite(run_cost) or run_cost < 0: raise ValueError('Run cost unavailable')
        total += run_cost
    if total > budget: raise ValueError(f'Reported cost ${total:.4f} exceeds ${budget:.2f} budget')
    if len(completed) >= 2:
        if any(calls_by_model[x] == 0 for x in LABELS): raise ValueError('First two runs did not cover all model families; inspect before continuing')
        highest_mean = max(cost_by_model[x] / calls_by_model[x] for x in LABELS)
        remaining = len(jobs) - len(completed)
        projected = (total + remaining * 36 * highest_mean) * 1.3
        if projected > budget: raise ValueError(f'Conservative projected cost including 30% reserve ${projected:.4f} exceeds ${budget:.2f} budget')
    else:
        projected = None
    return {'completed': len(completed), 'planned': len(jobs) - len(completed), 'reported_cost_usd': total, 'projected_with_reserve_usd': projected, 'budget_usd': budget}


def run(root, preflight, budget, reviewed_invalid=None):
    if not math.isfinite(budget) or budget <= 0: raise ValueError('Budget must be positive')
    if not os.environ.get('OPENROUTER_API_KEY'): raise RuntimeError('Set OPENROUTER_API_KEY in this terminal; no run was started')
    output = root/'AUTO_CALIBRATION.md'
    if output.exists() and not reviewed_invalid: raise FileExistsError('Choose a new study; unattended summary already exists')
    if reviewed_invalid and not output.exists(): raise ValueError('A prior unattended summary is required to continue after review')
    def note(message):
        print(message, flush=True)
        with output.open('a') as f: f.write(message + '\n\n')
    note(('# Reviewed continuation: ' + reviewed_invalid + '\n\nOne recorded invalid action is retained and remains visible in the results.' if reviewed_invalid else '# Unattended calibration') + '\n\nReported-cost guard only; actual billing may differ and the limit is not enforced within a run.')
    try:
        info = assess(root, preflight, budget, reviewed_invalid)
        if reviewed_invalid:
            plan = read(root/'plan.json')
            reviewed = [j for j in plan['jobs'] if j['id'] == reviewed_invalid and j['status'] == 'completed']
            if info['completed'] != 4 or len(reviewed) != 1 or read(root/reviewed_invalid/'metrics.json')['invalid_actions'] != 1:
                raise ValueError('Reviewed continuation requires exactly four completed runs and one recorded invalid action in the specified run')
        elif info['completed'] != 0: raise ValueError('Unattended calibration requires a fresh study')
        for index in range(info['completed'], 5):
            if index:
                interval = read(root/'plan.json')['request_interval_seconds']
                print(f'Waiting {interval:g} seconds between runs.', flush=True)
                time.sleep(interval)
            execute(SimpleNamespace(study=str(root), preflight=str(preflight), mock=False, limit=1))
            info = assess(root, preflight, budget, reviewed_invalid)
            note(f"Completed {info['completed']}/5; reported cost including preflight ${info['reported_cost_usd']:.6f}; projected including reserve " + (f"${info['projected_with_reserve_usd']:.4f}." if info['projected_with_reserve_usd'] is not None else 'available after two runs.'))
        export_path = root.parent/(root.name+'-auto-export.json')
        report_path = root.parent/(root.name+'-auto-summary.md')
        export(SimpleNamespace(study=str(root), output=str(export_path)))
        report(SimpleNamespace(export=str(export_path), output=str(report_path)))
        note(f'Completed all five runs. Metrics summary: {report_path}.')
    except Exception as exc:
        note(f'STOPPED: {type(exc).__name__}: {exc}. Preserve the study and inspect logs and billing before any new attempt.')
        raise


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--study', type=Path, required=True); p.add_argument('--preflight', type=Path, required=True)
    p.add_argument('--reported-budget', type=float, required=True)
    p.add_argument('--reviewed-invalid-run', help='continue one remaining run after explicitly reviewing one recorded invalid action')
    args = p.parse_args(); run(args.study, args.preflight, args.reported_budget, args.reviewed_invalid_run)


if __name__ == '__main__': main()
