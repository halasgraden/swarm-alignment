"""Run a paid model review for each completed study run and collect ratings in one file."""
import argparse
from pathlib import Path
from .evaluate_assistance import evaluate
from .study import read


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--study', type=Path, required=True); p.add_argument('--review-dir', type=Path, required=True)
    p.add_argument('--model', required=True); p.add_argument('--provider', required=True); p.add_argument('--limit', type=int, required=True)
    a = p.parse_args()
    if a.limit < 1: p.error('--limit must be positive')
    plan = read(a.study/'plan.json')
    if plan.get('schema') not in ('assistance-v1', 'assistance-v2', 'assistance-v3', 'assistance-v4', 'assistance-v5', 'assistance-v6', 'assistance-v7'): raise ValueError('Incompatible study schema')
    jobs = [j for j in plan['jobs'] if j['status'] == 'completed'][:a.limit]
    if not jobs: raise ValueError('No completed runs to review')
    a.review_dir.mkdir(parents=True, exist_ok=False)
    summary = a.review_dir/'MODEL_SCORE_SUMMARY.md'
    with summary.open('x') as f:
        f.write('# Model-reviewed score summary\n\nPrivate: review before sharing. Model ratings are subjective; verify cited steps and reasoning.\n\n')
        for index, job in enumerate(jobs):
            output = a.review_dir/(job['id'] + '.md')
            raw = a.review_dir/(job['id'] + '-private.json')
            try:
                evaluate(a.study/job['id'], output, a.model, a.provider, raw, index + 1)
                f.write(output.read_text() + '\n')
            except Exception as exc:
                f.write(f"## {job['id']} — review failed\n\n{type(exc).__name__}: {exc}\n")
                f.flush()
                raise
            f.flush()
    print(f'Combined model scores: {summary}')


if __name__ == '__main__': main()
