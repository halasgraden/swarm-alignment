"""Check OpenRouter API authentication without generating model output."""
import os
import sys
import urllib.error
import urllib.request

def check_key():
    key=os.environ.get('OPENROUTER_API_KEY','')
    if not key: return False, 'OPENROUTER_API_KEY is not set in this terminal.'
    if key != key.strip() or any(c.isspace() for c in key):
        return False, 'OPENROUTER_API_KEY contains whitespace. Re-enter the key only.'
    request=urllib.request.Request('https://openrouter.ai/api/v1/key',headers={'Authorization':'Bearer '+key})
    try:
        with urllib.request.urlopen(request,timeout=20) as response:
            if response.status != 200: return False, f'OpenRouter returned HTTP {response.status}.'
    except urllib.error.HTTPError as exc:
        if exc.code==401: return False, 'OpenRouter rejected the key (HTTP 401). Re-enter an active OpenRouter API key.'
        return False, f'OpenRouter returned HTTP {exc.code}.'
    except (urllib.error.URLError,TimeoutError):
        return False, 'Could not reach OpenRouter. Check your network connection.'
    return True, 'OpenRouter accepted the API key. This checks authentication only, not model access or credits.'

def main():
    ok,message=check_key()
    print(message, file=sys.stdout if ok else sys.stderr)
    return 0 if ok else 1

if __name__=='__main__': sys.exit(main())
