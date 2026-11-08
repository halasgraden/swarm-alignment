"""Extract only readable reasoning text; encrypted blocks are not text."""
def reasoning_text(message):
    if isinstance(message.get('reasoning'),str) and message['reasoning'].strip(): return message['reasoning']
    if isinstance(message.get('thinking'),str) and message['thinking'].strip(): return message['thinking']
    details=message.get('reasoning_details') or []
    if not isinstance(details,list): return ''
    return '\n'.join(d['text'] for d in details if isinstance(d,dict) and 'encrypted' not in str(d.get('type', '')).lower() and isinstance(d.get('text'),str) and d['text'].strip())
