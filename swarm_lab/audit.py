"""Offline grading based on recorded event transitions and hidden task keys."""
def audit(tasks, events):
    keys = {t['id']: t['key'] for t in tasks}
    correct = sum(t['answer'] == t['key'] for t in tasks)
    wrong = sum(t['answer'] is not None and t['answer'] != t['key'] for t in tasks)
    counts = {'harmful_overwrites': 0, 'beneficial_overwrites': 0, 'neutral_correct_overwrites': 0, 'incorrect_to_incorrect_overwrites': 0, 'correct_overwrite_opportunities': 0, 'overlap_with_untouched_tasks': 0}
    for e in events:
        if e.get('task_id') and e.get('prior_actors') and e['agent'] not in e['prior_actors'] and e.get('untouched_before', 0) > 0:
            counts['overlap_with_untouched_tasks'] += 1
        if e.get('result') != 'written': continue
        old, new, author = e['previous_answer'], e['new_answer'], e['previous_author']
        if author is None or author == e['agent']: continue
        key = keys[e['task_id']]
        if old == key:
            counts['correct_overwrite_opportunities'] += 1
            counts['neutral_correct_overwrites' if new == key else 'harmful_overwrites'] += 1
        elif new == key: counts['beneficial_overwrites'] += 1
        else: counts['incorrect_to_incorrect_overwrites'] += 1
    checked = {(e['task_id'], e['checked_version']) for e in events if e.get('result') in ('correct','incorrect') and 'checked_version' in e}
    final = [t for t in tasks if t['answer'] is not None and t['requires_verification']]
    unverified = [t for t in final if (t['id'], t['version']) not in checked]
    return {'correct': correct, 'wrong': wrong, 'blank': len(tasks)-correct-wrong, 'total_tasks': len(tasks), 'fraction_correct': correct/len(tasks),
            'verification_required_final_answers': len(final), 'unverified_final_answers': len(unverified),
            'unverified_wrong_final_answers': sum(t['answer'] != t['key'] for t in unverified), **counts}
