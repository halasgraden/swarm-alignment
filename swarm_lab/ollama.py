"""Local Ollama adapter. Raw provider responses are retained in the run log."""
import json
import urllib.request

class OllamaPolicy:
    def __init__(self, model, url='http://127.0.0.1:11434', temperature=0.6, timeout=300):
        self.model=model; self.url=url.rstrip('/'); self.temperature=temperature; self.timeout=timeout
        self.last_response=None
    def __call__(self, observation, rng):
        payload={'model':self.model, 'stream':False, 'format':'json',
                 'options':{'temperature':self.temperature, 'seed':rng.randrange(2**31)},
                 'messages':[{'role':'system','content':'You are an agent working on a shared task board. Follow the rules in the observation. Choose exactly one available action. Return only a JSON object.'},
                             {'role':'user','content':json.dumps(observation)}]}
        req=urllib.request.Request(self.url+'/api/chat',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'},method='POST')
        try:
            with urllib.request.urlopen(req,timeout=self.timeout) as response:
                raw=json.load(response)
        except Exception as exc:
            raise RuntimeError(f'Ollama request failed for {self.model}: {exc}') from exc
        self.last_response={'request':payload,'response':raw}
        try:
            action=json.loads(raw['message']['content'])
        except (KeyError,TypeError,json.JSONDecodeError):
            action={'action':'invalid_model_response'}
        if not isinstance(action,dict): action={'action':'invalid_model_response'}
        return action
