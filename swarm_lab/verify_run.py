"""Check saved artifact digests and optionally compare recorded source hashes."""
import argparse
import hashlib
import json
from pathlib import Path

def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def verify(path):
    manifest=json.loads((path/'manifest.json').read_text())
    hashes=manifest.get('artifact_sha256')
    if not hashes: raise ValueError('No artifact hashes in manifest; cannot verify this run')
    failures=[]
    for name, expected in hashes.items():
        p=path/name
        if not p.is_file(): failures.append(f'missing: {name}')
        elif digest(p)!=expected: failures.append(f'changed: {name}')
    recorded=manifest.get('source_sha256',{})
    source=Path(__file__).parent
    source_differences=[name for name,value in recorded.items() if not (source/name).is_file() or digest(source/name)!=value]
    return {'status':manifest['status'],'artifact_errors':failures,'source_differences':source_differences,
            'note':'The manifest is not signed. Store its hash externally for tamper evidence.'}

def main():
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('run_dir'); a=p.parse_args()
    result=verify(Path(a.run_dir)); print(json.dumps(result,indent=2))
    if result['artifact_errors']: raise SystemExit(1)

if __name__=='__main__': main()
