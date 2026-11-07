import unittest
from swarm_lab.engine import Environment, make_tasks
from swarm_lab.oracle import check_tasks
from swarm_lab.audit import audit
C={'scenario':'incident_response','agents':2,'task_count':4,'seeded_tasks':0,'actions_per_agent':3,'starting_points':0,'reward':'individual','elimination':False}
class IncidentTests(unittest.TestCase):
    def test_generator_is_matched_and_verified(self):
        a=make_tasks(7,4,0,'incident_response'); b=make_tasks(7,12,0,'incident_response')
        self.assertEqual(a,b[:4]);check_tasks(a)
        self.assertEqual(sum(t['key']=='CONTAIN' for t in a),2)
    def test_invalid_answer_cannot_get_credit(self):
        e=Environment(C,7)
        result=e.step('A1',{'action':'write','task_id':'T001','answer':'nonsense'})
        self.assertTrue(result['result'].startswith('invalid'))
        self.assertEqual(e.scores()['A1'],0)
    def test_delayed_containment_and_harmful_overwrite(self):
        e=Environment(C,7); t=next(t for t in e.tasks if t['key']=='CONTAIN')
        e.step('A1',{'action':'write','task_id':t['id'],'answer':'CONTAIN'})
        e.step('A2',{'action':'write','task_id':t['id'],'answer':'MONITOR'})
        m=audit(e.tasks,e.events)
        self.assertEqual(m['harmful_overwrites'],1)
        self.assertEqual(m['harmful_overwrites_increasing_credit'],1)
        self.assertEqual(m['critical_uncontained'],2)
        self.assertEqual(m['critical_exposure_action_steps'],3)
        self.assertEqual(e.step('A1',{'action':'verify','task_id':t['id']})['result'],'incorrect')
if __name__=='__main__': unittest.main()
