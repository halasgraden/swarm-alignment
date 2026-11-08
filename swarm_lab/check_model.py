"""Check OpenRouter's public endpoint listing without using an API key."""
import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

def check_model(model):
    parts=model.split('/')
    if len(parts)!=2 or not all(parts):
        raise ValueError('Model must have the form author/model')
    path='/'.join(urllib.parse.quote(part,safe='-.:') for part in parts)
    req=urllib.request.Request('https://openrouter.ai/api/v1/models/'+path+'/endpoints')
    try:
        with urllib.request.urlopen(req,timeout=20) as response: data=json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f'OpenRouter endpoint lookup returned HTTP {exc.code} for {model}') from None
    except (urllib.error.URLError,TimeoutError):
        raise RuntimeError('Could not reach OpenRouter to check model endpoints') from None
    endpoints=data.get('data',{}).get('endpoints',[])
    if not isinstance(endpoints,list): raise RuntimeError('Unexpected OpenRouter endpoint response')
    return [{'provider':x.get('provider_name'), 'tag':x.get('tag'),
             'supports_reasoning':'reasoning' in (x.get('supported_parameters') or []),
             'supports_response_format':'response_format' in (x.get('supported_parameters') or [])}
            for x in endpoints if isinstance(x,dict)]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--config',required=True); a=p.parse_args()
    try:
        config=json.loads(Path(a.config).read_text()); model=config['inference']['model']
        endpoints=check_model(model)
    except (KeyError,ValueError,RuntimeError,OSError) as exc:
        print(f'Error: {exc}',file=sys.stderr); return 1
    print(f'Model: {model}\nPublic endpoints: {len(endpoints)}')
    for endpoint in endpoints:
        print(f"  {endpoint['provider']} ({endpoint['tag']}): reasoning={endpoint['supports_reasoning']}, JSON format={endpoint['supports_response_format']}")
    print('Public listing only: account privacy settings, provider restrictions, and live availability may differ.')
    return 0 if endpoints else 1

if __name__=='__main__': sys.exit(main())
