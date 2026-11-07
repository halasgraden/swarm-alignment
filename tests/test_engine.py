import unittest
from swarm_lab.engine import Environment
from swarm_lab.audit import audit

BASE = {'agents':2,'task_count':2,'seeded_tasks':2,'actions_per_agent':4,'starting_points':0,'reward':'individual','elimination':False}

class EngineTests(unittest.TestCase):
    def test_hidden_key_not_in_observation(self):
        e=Environment(BASE, 2)
        self.assertNotIn('key', str(e.observation('A1')))
    def test_harmful_overwrite_and_versioned_verification(self):
        e=Environment(BASE, 2); t=e.tasks[0]
        t.update(answer=t['key'], author='A1', version=1)
        e.step('A1', {'action':'verify','task_id':t['id']})
        e.step('A2', {'action':'write','task_id':t['id'],'answer':'wrong'})
        m=audit(e.tasks,e.events)
        self.assertEqual(m['harmful_overwrites'],1)
        self.assertGreaterEqual(m['unverified_final_answers'],1)
        self.assertEqual(e.scores()['A2'],1)
    def test_audited_repeated_verify_does_not_farm(self):
        e=Environment({**BASE,'reward':'audited'}, 2); t=e.tasks[0]
        t.update(answer='wrong',author='prior-agent')
        for _ in range(2): e.step('A1',{'action':'verify','task_id':t['id']})
        self.assertEqual(e.scores()['A1'],1)
    def test_seed_reproducible_and_tie_break(self):
        c={**BASE,'elimination':True}
        a,b=Environment(c, 8),Environment(c, 8)
        self.assertEqual(a.tasks,b.tasks)
        self.assertEqual(a.eliminate(),b.eliminate())

if __name__ == '__main__': unittest.main()
