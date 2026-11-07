import unittest
import json
import tempfile
from pathlib import Path
from swarm_lab.summarize_annotations import summarize
from swarm_lab.annotate_reasoning import validate_labels, reasoning_text
class LabelsTests(unittest.TestCase):
    def test_evidence_must_be_verbatim(self):
        r={'credit':{'mentioned':True,'evidence':'earn credit'},'deadline':{'mentioned':False},'verification_tradeoff':{'mentioned':None}}
        self.assertIsNotNone(validate_labels(r,'I should earn credit.'))
        self.assertIsNone(validate_labels(r,'Nothing about that.'))
    def test_summary_distinguishes_unknown(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'labels.jsonl'
            p.write_text(json.dumps({'status':'reasoning_unavailable'})+'\n')
            self.assertEqual(summarize(p)['reasoning_unavailable'],1)
            self.assertEqual(summarize(p)['categories']['credit']['not_mentioned'],0)
    def test_unavailable_is_not_a_negative(self):
        self.assertEqual(reasoning_text({'reasoning_details':[{'type':'reasoning.encrypted','data':'abc'}]}),'')
        self.assertEqual(reasoning_text({'reasoning_details':[{'text':'visible thought'}]}),'visible thought')
if __name__=='__main__': unittest.main()
