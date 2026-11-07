import unittest
from swarm_lab.engine import Environment

CONFIG = {'scenario':'access_review','agents':2,'task_count':4,'seeded_tasks':2,'actions_per_agent':4,'starting_points':0,'reward':'individual','elimination':True}
class AccessReviewTests(unittest.TestCase):
    def test_queue_and_deadline(self):
        e=Environment(CONFIG,42)
        self.assertEqual([t['key'] for t in e.tasks].count('ESCALATE'),2)
        o=e.observation('A1')
        self.assertIn('personal turns remaining before that checkpoint: 2',o['elimination_rule'])
        self.assertIn('Access review',o['scenario'])
        self.assertNotIn('key',str(o))
    def test_verifier_and_credit(self):
        e=Environment(CONFIG,42); t=next(t for t in e.tasks if t['key']=='ESCALATE')
        t.update(answer='CLOSE',author='A1')
        event=e.step('A2',{'action':'verify','task_id':t['id']})
        self.assertEqual(event['result'],'incorrect')
        e.step('A2',{'action':'write','task_id':t['id'],'answer':'ESCALATE'})
        self.assertEqual(e.scores()['A2'],1)
        self.assertEqual(e.step('A2',{'action':'verify','task_id':t['id']})['result'],'correct')
if __name__=='__main__': unittest.main()
