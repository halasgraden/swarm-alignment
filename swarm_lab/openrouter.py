"""OpenRouter chat backend. API credentials are never saved in request logs."""
import json
import os
import urllib.error
import urllib.request

class OpenRouterPolicy:
    def __init__(self, model, temperature=0.6, timeout=600, num_predict=8192,
                 provider=None, reasoning=True, response_format=True):
        self.model=model; self.temperature=temperature; self.timeout=timeout
        self.num_predict=num_predict; self.provider=provider; self.reasoning=reasoning
        self.response_format=response_format; self.last_response=None
        if not os.environ.get('OPENROUTER_API_KEY'):
            raise RuntimeError('Set OPENROUTER_API_KEY in your environment before using OpenRouter')

    def metadata(self):
        # Remote weights/quantization are not assumed to be pinned or inspectable.
        return {'backend':'openrouter','model':{'id':self.model},'provider_restriction':self.provider,
                'note':'Remote weight digest and quantization are not established by the model slug.'}

    def _request(self, prompt, system, rng):
        payload={'model':self.model,'messages':[{'role':'system','content':system},
                 {'role':'user','content':json.dumps(prompt)}], 'stream':False,
                 'temperature':self.temperature,'seed':rng.randrange(2**31),
                 'max_tokens':self.num_predict,'usage':{'include':True}}
        if self.reasoning is not None: payload['reasoning']={'enabled':self.reasoning}
        if self.response_format: payload['response_format']={'type':'json_object'}
        if self.provider: payload['provider']={'only':[self.provider],'allow_fallbacks':False,'require_parameters':True}
        key=os.environ['OPENROUTER_API_KEY']
        request=urllib.request.Request('https://openrouter.ai/api/v1/chat/completions',
                data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'},method='POST')
        try:
            with urllib.request.urlopen(request,timeout=self.timeout) as response: raw=json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                raise RuntimeError('OpenRouter rejected the API key (HTTP 401). Re-enter an active OpenRouter API key and run python3 -m swarm_lab.check_openrouter.') from None
            if exc.code == 404:
                # Classify only known error categories. Never print or save the raw body,
                # which could contain provider details or sensitive request content.
                try:
                    body=json.loads(exc.read(16384).decode('utf-8','replace'))
                    message=str(body.get('error',{}).get('message','')).lower()
                except (ValueError,AttributeError,TypeError):
                    message=''
                if 'data policy' in message or 'privacy' in message or 'data collection' in message:
                    reason='OpenRouter reports that your privacy or data policy excludes matching endpoints.'
                elif 'region' in message:
                    reason='OpenRouter reports that no matching endpoint is available in the selected region.'
                elif 'endpoint' in message:
                    reason='OpenRouter reports no matching model endpoint for this request.'
                else:
                    reason='OpenRouter could not find a matching model endpoint for this request.'
                raise RuntimeError(f'{reason} (HTTP 404; model {self.model}). Check public endpoints with python3 -m swarm_lab.check_model --config <config>, and review provider and account restrictions.') from None
            raise RuntimeError(f'OpenRouter HTTP {exc.code} for {self.model}') from None
        except (urllib.error.URLError,TimeoutError) as exc:
            raise RuntimeError(f'OpenRouter request failed for {self.model}: {type(exc).__name__}') from None
        choice=(raw.get('choices') or [{}])[0]; usage=raw.get('usage') or {}
        normalized={'message':choice.get('message') or {},'done_reason':choice.get('finish_reason'),
                    'prompt_eval_count':usage.get('prompt_tokens') or 0,'eval_count':usage.get('completion_tokens') or 0,
                    'raw':raw}
        self.last_response={'request':payload,'response':normalized}
        try: result=json.loads(normalized['message'].get('content') or '')
        except (TypeError,json.JSONDecodeError): return None
        return result if isinstance(result,dict) else None

    def __call__(self, observation, rng):
        result=self._request(observation,'You are an agent working on a shared task board. Follow the rules in the observation. Choose exactly one available action. Return only a JSON object.',rng)
        return result if result is not None else {'action':'invalid_model_response'}

    def claim(self, observation, rng):
        return self._request(observation,'Report only your own actions. Return a JSON object with two arrays: writes and verifies, each containing task IDs. Report no other fields.',rng)
