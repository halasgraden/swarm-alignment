import json
import unittest
from pathlib import Path
class ModelConfigs(unittest.TestCase):
    def test_four_distinct_families(self):
        root=Path(__file__).resolve().parent.parent/'configs'
        names=['qwen','gpt-oss','deepseek','mistral']
        configs=[json.loads((root/f'openrouter-{n}.json').read_text()) for n in names]
        ids=[x['inference']['model'] for x in configs]
        self.assertEqual(len(set(ids)),4)
        self.assertEqual(len({x.split('/')[0] for x in ids}),4)
        self.assertTrue(all(x['scenario']=='incident_response' for x in configs))
if __name__=='__main__':unittest.main()
