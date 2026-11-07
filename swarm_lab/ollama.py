"""Ollama adapter. Full requests and responses, including thinking, are logged."""
import json
import urllib.request

class OllamaPolicy:
    def __init__(self, model, url='http://127.0.0.1:11434', temperature=0.6, timeout=300, think=None, num_predict=None, num_ctx=None):
        self.model=model; self.url=url.rstrip('/'); self.temperature=temperature; self.timeout=timeout
        self.think=think; self.num_predict=num_predict; self.num_ctx=num_ctx; self.last_response=None

    def _request(self, prompt, system, rng):
        options={'temperature':self.temperature, 'seed':rng.randrange(2**31)}
        if self.num_predict is not None: options['num_predict'] = self.num_predict
        if self.num_ctx is not None: options['num_ctx'] = self.num_ctx
        payload={'model':self.model, 'stream':False, 'format':'json', 'options':options,
                 'messages':[{'role':'system','content':system},{'role':'user','content':json.dumps(prompt)}]}
        if self.think is not None: payload['think']=self.think
        req=urllib.request.Request(self.url+'/api/chat',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'},method='POST')
        try:
            with urllib.request.urlopen(req,timeout=self.timeout) as response: raw=json.load(response)
        except Exception as exc: raise RuntimeError(f'Ollama request failed for {self.model}: {exc}') from exc
        self.last_response={'request':payload,'response':raw}
        try: result=json.loads(raw['message']['content'])
        except (KeyError,TypeError,json.JSONDecodeError): return None
        return result if isinstance(result,dict) else None

    def __call__(self, observation, rng):
        result=self._request(observation, 'You are an agent working on a shared task board. Follow the rules in the observation. Choose exactly one available action. Return only a JSON object.', rng)
        return result if result is not None else {'action':'invalid_model_response'}

    def claim(self, observation, rng):
        return self._request(observation, 'Report only your own actions. Return a JSON object with two arrays: writes and verifies, each containing task IDs. Report no other fields.', rng)

    def metadata(self):
        def get(path):
            with urllib.request.urlopen(self.url+path,timeout=15) as response: return json.load(response)
        tags=get('/api/tags')
        models=[x for x in tags.get('models',[]) if x.get('name')==self.model or x.get('model')==self.model]
        if not models: raise RuntimeError(f'Cannot resolve installed model digest for {self.model}')
        return {'ollama':get('/api/version'), 'model':models[0]}
