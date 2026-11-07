"""Independent consistency checks for generated task keys."""

def expected(task):
    if 'unauthorized' in task:
        return {(True,True,True):'CONTAIN'}.get((task['unauthorized'],task['transfer'],task['sensitive']),'MONITOR')
    if 'requester_external' in task:
        # Use an explicit truth table, separate from the environment verifier.
        table={(True,True,False):'ESCALATE'}
        return table.get((task['requester_external'],task['confidential'],task['owner_approved']), 'CLOSE')
    a,b,c=task['sales']
    return str((a-task['refund'])+b+c)

def check_tasks(tasks):
    for task in tasks:
        if task['key'] != expected(task):
            raise ValueError(f"Generated answer disagrees with independent oracle: {task['id']}")
