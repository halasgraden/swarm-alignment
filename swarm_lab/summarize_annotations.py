"""Count exploratory text labels while keeping missing and invalid cases explicit."""
import argparse
import json
from pathlib import Path
from .annotate_reasoning import CATEGORIES

def summarize(path):
    result={'total_records':0,'reasoning_unavailable':0,'invalid_label':0,'annotated':0,
            'categories':{k:{'mentioned':0,'not_mentioned':0,'unclear':0} for k in CATEGORIES}}
    for line in path.read_text().splitlines():
        r=json.loads(line);result['total_records']+=1
        status=r['status']
        if status!='ok':
            if status not in ('reasoning_unavailable','invalid_label'): raise ValueError(f'Unexpected status: {status}')
            result[status]+=1;continue
        result['annotated']+=1
        for cat in CATEGORIES:
            v=r['labels'][cat]['mentioned']
            result['categories'][cat]['mentioned' if v is True else 'not_mentioned' if v is False else 'unclear']+=1
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('labels');a=p.parse_args()
    print(json.dumps(summarize(Path(a.labels)),indent=2))
if __name__=='__main__':main()
