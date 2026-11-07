import json
import random
import unittest
from unittest.mock import patch
from swarm_lab.ollama import OllamaPolicy

class Response:
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def read(self): return json.dumps({'message':{'content':'{"action":"pass"}'},'eval_count':3}).encode()

class AdapterTests(unittest.TestCase):
    @patch('urllib.request.urlopen', return_value=Response())
    def test_request_and_raw_response_recorded(self, call):
        p=OllamaPolicy('olmo-3:7b-instruct')
        self.assertEqual(p({'agent':'A1'},random.Random(4)),{'action':'pass'})
        self.assertEqual(p.last_response['response']['eval_count'],3)
        self.assertEqual(p.last_response['request']['model'],'olmo-3:7b-instruct')
        self.assertEqual(call.call_count,1)

if __name__=='__main__': unittest.main()
