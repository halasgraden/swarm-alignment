import io
import json
import os
import random
import unittest
import urllib.error
from unittest.mock import patch
from swarm_lab.check_model import check_model
from swarm_lab.openrouter import OpenRouterPolicy

class Response:
    def __init__(self,data): self.data=data
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def read(self): return json.dumps(self.data).encode()

class EndpointTests(unittest.TestCase):
    @patch('urllib.request.urlopen',return_value=Response({'data':{'endpoints':[]}}))
    def test_empty_list_is_not_a_working_endpoint(self,request):
        self.assertEqual(check_model('qwen/example'),[])
    @patch('urllib.request.urlopen',return_value=Response({'data':{'endpoints':[{'provider_name':'Host','tag':'host/fp8','supported_parameters':['reasoning','response_format']}]}}))
    def test_public_capabilities(self,request):
        self.assertEqual(check_model('qwen/example')[0],{'provider':'Host','tag':'host/fp8','supports_reasoning':True,'supports_response_format':True})
    @patch.dict(os.environ,{'OPENROUTER_API_KEY':'sensitive-secret'})
    def test_404_does_not_leak_error_body_or_key(self):
        body=json.dumps({'error':{'message':'No endpoints found: sensitive-secret'}}).encode()
        e=urllib.error.HTTPError('https://example',404,'Not found',{},io.BytesIO(body))
        with patch('urllib.request.urlopen',side_effect=e):
            with self.assertRaisesRegex(RuntimeError,'no matching model endpoint') as cm:
                OpenRouterPolicy('qwen/example')({'agent':'A1'},random.Random(1))
        self.assertNotIn('sensitive-secret',str(cm.exception))
    @patch.dict(os.environ,{'OPENROUTER_API_KEY':'sensitive-secret'})
    def test_404_privacy_policy_diagnosis(self):
        e=urllib.error.HTTPError('https://example',404,'Not found',{},io.BytesIO(b'{"error":{"message":"No endpoints found matching your data policy"}}'))
        with patch('urllib.request.urlopen',side_effect=e):
            with self.assertRaisesRegex(RuntimeError,'privacy or data policy'):
                OpenRouterPolicy('qwen/example')({'agent':'A1'},random.Random(1))
if __name__=='__main__':unittest.main()
