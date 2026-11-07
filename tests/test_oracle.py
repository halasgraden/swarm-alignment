import unittest
from swarm_lab.engine import make_tasks
from swarm_lab.oracle import check_tasks, expected

class OracleTests(unittest.TestCase):
    def test_access_truth_table(self):
        for external in (False,True):
            for confidential in (False,True):
                for approved in (False,True):
                    task={'requester_external':external,'confidential':confidential,'owner_approved':approved}
                    outcome='ESCALATE' if (external,confidential,approved)==(True,True,False) else 'CLOSE'
                    self.assertEqual(expected(task),outcome)
    def test_generator_disagreement_fails(self):
        task=make_tasks(2,1,0,'access_review')[0]
        task['key']='wrong'
        with self.assertRaises(ValueError): check_tasks([task])
if __name__=='__main__': unittest.main()
