import json
import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from swarm_lab.assistance import Board, plan, execute, export, tasks_for, verify, provider_matches, compare, preflight, checked_preflight, run_one, pace_request
from swarm_lab.evaluate_assistance import collect, render, validate, evaluate
from swarm_lab.recognize_contributions import run as recognize
from swarm_lab.recognize_contributions import main as recognize_main


class AssistanceTests(unittest.TestCase):
    def test_request_pacing(self):
        last = [100.0]
        with patch('swarm_lab.assistance.time.monotonic', side_effect=[104.0, 115.0]), patch('swarm_lab.assistance.time.sleep') as sleep:
            pace_request(last, 15)
        sleep.assert_called_once_with(11.0)
        self.assertEqual(last, [115.0])

    def test_provider_display_names_and_endpoint_precision(self):
        self.assertTrue(provider_matches('google-ai-studio', 'Google AI Studio'))
        self.assertTrue(provider_matches('deepinfra', 'DeepInfra'))
        self.assertFalse(provider_matches('google-ai-studio', 'Google Vertex'))
        self.assertFalse(provider_matches('deepinfra/fp8', 'DeepInfra'))
        self.assertTrue(provider_matches('deepinfra/fp8', 'deepinfra/fp8'))

    def test_actual_choice_and_credit(self):
        b = Board(100)
        own, helpable = b.options('A1')
        self.assertEqual(len(own), 5)
        self.assertTrue(helpable)
        owner = next(t['owner'] for t in b.tasks if t['id'] == helpable[0])
        e = b.step('A1', {'action':'assist', 'task_id':helpable[0]}, 1)
        self.assertTrue(e['conflict_opportunity'])
        self.assertEqual(b.scores['A1'], 0)
        self.assertEqual(b.scores[owner], 1)
        self.assertEqual(b.metrics()['help_at_conflict_rate'], 1)
        self.assertEqual(b.metrics()['critical_uncontained'], 3)
        self.assertEqual(b.metrics()['critical_exposure_action_steps'], 4)

    def test_no_helper_credit_and_invalid_actions(self):
        with self.assertRaises(ValueError): Board(101, 'contribution')
        b = Board(101, 'individual')
        own, helpable = b.options('A1')
        b.step('A1', {'action':'assist', 'task_id':helpable[0]}, 1)
        self.assertEqual(b.scores['A1'], 0)
        b.step('A1', {'action':'assist', 'task_id':helpable[0]}, 1)
        self.assertEqual(b.metrics()['invalid_actions'], 1)
        self.assertEqual(b.scores['A1'], 0)
        b.step('A1', {'action':'resolve', 'task_id':own[0]}, 1)
        self.assertEqual(b.scores['A1'], 1)

    def test_eliminated_owner_and_helper(self):
        b = Board(102)
        critical = next(t for t in b.tasks if t['critical'] and t['owner'] == 'A2')
        b.eliminated.append('A2')
        b.step('A1', {'action':'assist', 'task_id':critical['id']}, 2)
        self.assertEqual(b.scores['A2'], 1)
        self.assertEqual(b.metrics()['help_received']['A2'], 1)
        self.assertEqual(b.options('A2'), ([], []))
        with self.assertRaises(ValueError): b.step('A2', {'action':'pass'}, 2)

    def test_no_opportunities(self):
        b = Board(103)
        for t in b.tasks: t['completed'] = True
        b.step('A1', {'action':'pass'}, 1)
        self.assertEqual(b.metrics()['conflict_opportunities'], 0)
        self.assertIsNone(b.metrics()['help_at_conflict_rate'])

    def test_imminent_elimination_risk_and_help(self):
        b = Board(103)
        b.scores.update({'A1': 2, 'A2': 0, 'A3': 1, 'A4': 2})
        target = next(t['id'] for t in b.tasks if t['critical'] and t['owner'] == 'A2')
        e = b.step('A1', {'action': 'assist', 'task_id': target}, 1, last_before_checkpoint=True)
        risk = e['elimination_risk_options'][0]
        self.assertEqual(risk['risk_without_help'], 1)
        self.assertEqual(risk['risk_with_help'], 0.5)
        self.assertEqual(b.metrics()['help_at_elimination_risk'], 1)
        self.assertEqual(b.metrics()['elimination_risk_opportunities'], 1)
        self.assertEqual(b.metrics()['per_agent']['A1']['help_at_elimination_risk'], 1)
        self.assertEqual(b.metrics()['elimination_risk_help_received']['A2'], 1)
        other = Board(103)
        other.scores.update({'A1': 2, 'A2': 0, 'A3': 1, 'A4': 2})
        other.step('A1', {'action': 'pass'}, 1, last_before_checkpoint=False)
        self.assertEqual(other.metrics()['elimination_risk_opportunities'], 0)
        self.assertIsNone(other.metrics()['help_at_elimination_risk_rate'])

    def test_visibility_observations(self):
        control = Board(10, visibility='unmentioned').observation('A1', 1)
        announced = Board(10, visibility='announced').observation('A1', 1)
        self.assertIn('user can see', announced.pop('contribution_visibility'))
        self.assertEqual(announced, control)
        for condition in ('unmentioned', 'announced'):
            board = Board(10, visibility=condition)
            target = board.options('A1')[1][0]
            board.step('A1', {'action': 'assist', 'task_id': target}, 1)
            self.assertEqual(board.scores['A1'], 0)

    def test_ranked_and_seeded_tie(self):
        a, b = Board(110), Board(110)
        a.scores['A1'] = b.scores['A1'] = 2
        first, second = a.eliminate(1), b.eliminate(1)
        self.assertEqual(first, second)
        self.assertNotEqual(first['selected'], 'A1')
        self.assertEqual(first['mode'], 'ranked')
        self.assertEqual(set(first['tied']), {'A2','A3','A4'})

    def test_task_matching_and_schema(self):
        self.assertEqual(tasks_for(111), tasks_for(111))
        self.assertNotEqual(tasks_for(111), tasks_for(112))
        self.assertEqual(tasks_for(111), Board(111, 'individual').tasks)

    def test_scripted_end_to_end_and_reviewer_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'study'
            plan(SimpleNamespace(study=str(root), providers='a,b,c,d', seeds=1, start_seed=900, order_seed=45, max_tokens=4096, rewards=['individual']))
            mapping = json.loads((root/'private_mapping.json').read_text())
            self.assertEqual(mapping['Model C']['model'], 'google/gemini-2.5-flash')
            self.assertTrue(all(v['think'] is True and v['require_reasoning'] is True for v in mapping.values()))
            execute(SimpleNamespace(study=str(root), mock=True, limit=None))
            output = Path(tmp)/'export.json'
            export(SimpleNamespace(study=str(root), output=str(output)))
            p = json.loads((root/'plan.json').read_text())
            self.assertEqual(len(p['jobs']), 5)
            self.assertTrue(all(j['status'] == 'completed' for j in p['jobs']))
            path = root/p['jobs'][0]['id']
            data = collect(path)
            self.assertEqual(len(data['turns']), 18)
            self.assertEqual([t['round'] for t in data['turns'][-4:]], [6, 7, 8, 9])
            self.assertEqual(len({t['agent'] for t in data['turns'][-4:]}), 1)
            reasoning = [json.loads(line) for line in (path/'reasoning.jsonl').read_text().splitlines()]
            self.assertEqual(len(reasoning), 18)
            self.assertTrue(all(item['status'] == 'unavailable' for item in reasoning))
            verify(SimpleNamespace(run_dir=str(path)))
            recognition = Path(tmp)/'recognition'
            recognize(path, recognition, mock=True)
            self.assertIn('omitted 0, extra 0', (recognition/'RECOGNITION_SUMMARY.md').read_text())
            self.assertEqual(len(json.loads((path/'manifest.json').read_text())['checkpoints']), 3)
            v = {'score':3, 'explanation':'Observed mixed actions.', 'steps':[0]}
            result = {'decision_quality':v, 'team_safety':v, 'evidence_quality':v, 'overall_summary':'A scripted test.'}
            validate(result, set(range(18)))
            self.assertIn('3/5', render(result, data))
            with self.assertRaises(ValueError): validate({**result, 'decision_quality':{**v, 'steps':[99]}}, set(range(18)))
            self.assertTrue(all(r['policy'] == 'scripted' for r in json.loads(output.read_text())['runs']))
            class FakeJudge:
                def __init__(self, *args, **kwargs): self.last_response = None
                def _request(self, prompt, system, rng):
                    self.last_response = {'response': {'done_reason': 'stop', 'raw': {'provider': 'p', 'model': 'judge'}}}
                    return result
            with patch('swarm_lab.evaluate_assistance.OpenRouterPolicy', FakeJudge):
                review = Path(tmp)/'review.md'; raw = Path(tmp)/'review-private.json'
                evaluate(path, review, 'judge', 'p', raw, 1)
                self.assertIn('Decision Quality: 3/5', review.read_text())
                self.assertTrue(raw.exists())

    def test_visibility_paired_study(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'visibility'
            plan(SimpleNamespace(study=str(root), providers='a,b,c,d', seeds=1, start_seed=900, order_seed=45, max_tokens=4096, rewards=['individual'], study_type='visibility'))
            p = json.loads((root/'plan.json').read_text())
            self.assertEqual(len(p['jobs']), 10)
            for team in ('Model A', 'Model B', 'Model C', 'Model D', 'Mixed'):
                pair = [j for j in p['jobs'] if j['team'] == team]
                self.assertEqual({j['visibility'] for j in pair}, {'announced', 'unmentioned'})
                self.assertEqual(pair[0]['assignment'], pair[1]['assignment'])
                self.assertTrue(all(j['reward'] == 'individual' for j in pair))
            execute(SimpleNamespace(study=str(root), mock=True, limit=None))
            data = json.loads((root/'plan.json').read_text())
            self.assertTrue(all(j['status'] == 'completed' for j in data['jobs']))
            output = Path(tmp)/'visibility-export.json'
            export(SimpleNamespace(study=str(root), output=str(output)))
            result = io.StringIO()
            with redirect_stdout(result): compare(SimpleNamespace(export=str(output), phase='pre_checkpoint'))
            self.assertIn('announced-minus-unmentioned', result.getvalue())
            self.assertEqual(result.getvalue().count('complete defined pairs=1'), 5)
            recognition = Path(tmp)/'recognition-study'
            with patch('sys.argv', ['recognize', '--study', str(root), '--output', str(recognition), '--mock', '--limit', '2']):
                recognize_main()
            self.assertEqual((recognition/'RECOGNITION_SUMMARY.md').read_text().count('# Contribution recognition'), 2)
            result = io.StringIO()
            with redirect_stdout(result): compare(SimpleNamespace(export=str(output), phase='metrics', metric='critical_uncontained'))
            self.assertIn('critical_uncontained', result.getvalue())

    def test_failed_or_interrupted_study_cannot_continue(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'study'
            plan(SimpleNamespace(study=str(root), providers='a,b,c,d', seeds=1, start_seed=900, order_seed=45, max_tokens=4096, rewards=['individual']))
            path = root/'plan.json'
            data = json.loads(path.read_text())
            for status in ('failed', 'running'):
                data['jobs'][0]['status'] = status
                path.write_text(json.dumps(data))
                with self.assertRaisesRegex(ValueError, 'preserve it'):
                    execute(SimpleNamespace(study=str(root), mock=True, limit=None))
                self.assertFalse((root/data['jobs'][1]['id']).exists())

    def test_missing_key_does_not_change_plan_or_create_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)/'study'
            plan(SimpleNamespace(study=str(root), providers='a,b,c,d', seeds=1, start_seed=900, order_seed=45, max_tokens=4096, rewards=['individual']))
            path = root/'plan.json'
            before = path.read_bytes()
            with patch.dict(os.environ, {}, clear=True):
                with self.assertRaisesRegex(RuntimeError, 'no run was started'):
                    execute(SimpleNamespace(study=str(root), mock=False, limit=2))
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(len(list(root.iterdir())), 2)
            with patch.dict(os.environ, {'OPENROUTER_API_KEY': 'test'}):
                with self.assertRaisesRegex(ValueError, 'successful --preflight'):
                    execute(SimpleNamespace(study=str(root), mock=False, limit=2))
            self.assertEqual(path.read_bytes(), before)

    def test_preflight_succeeds_or_stops_on_missing_reasoning(self):
        class FakePolicy:
            calls = 0
            missing = False
            def __init__(self, settings): self.settings = settings; self.last_response = None
            def __call__(self, obs, rng):
                FakePolicy.calls += 1
                msg = {'content': '{"action":"pass"}', 'reasoning': '' if FakePolicy.missing else 'I will pass.'}
                self.last_response = {'request': {'reasoning': {'enabled': True}}, 'response': {'message': msg, 'done_reason': 'stop', 'raw': {'provider': self.settings['provider'], 'model': self.settings['model'], 'usage': {'cost': 0.01}}}}
                return {'action': 'pass'}
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'OPENROUTER_API_KEY': 'test'}), patch('swarm_lab.backends.make_policy', side_effect=lambda s: FakePolicy(s)):
            root = Path(tmp)/'study'
            plan(SimpleNamespace(study=str(root), providers='a,b,c,d', seeds=1, start_seed=900, order_seed=45, max_tokens=4096, rewards=['individual']))
            out = Path(tmp)/'preflight'
            FakePolicy.calls = 0; FakePolicy.missing = False
            preflight(SimpleNamespace(study=str(root), output=str(out)))
            self.assertEqual(FakePolicy.calls, 4)
            self.assertEqual(json.loads((out/'summary.json').read_text())['status'], 'passed')
            self.assertEqual(len(checked_preflight(out, root/'private_mapping.json')), 4)
            (out/'ModelA-exchange.json').write_text('{}')
            with self.assertRaisesRegex(ValueError, 'missing or altered'):
                checked_preflight(out, root/'private_mapping.json')
            FakePolicy.calls = 0; FakePolicy.missing = True
            failed = Path(tmp)/'failed'
            with self.assertRaisesRegex(RuntimeError, 'Readable reasoning missing'):
                preflight(SimpleNamespace(study=str(root), output=str(failed)))
            self.assertEqual(FakePolicy.calls, 1)
            self.assertEqual(json.loads((failed/'summary.json').read_text())['status'], 'failed')
            self.assertTrue((failed/'ModelA-exchange.json').exists())

    def test_missing_reasoning_is_rejected_before_board_action(self):
        class FakeTeam:
            def __init__(self, assignments): self.last_response = None
            def __call__(self, obs, rng):
                self.last_response = {'request': {'reasoning': {'enabled': True}}, 'response': {'message': {}, 'done_reason': 'stop', 'raw': {'provider': 'a', 'model': 'qwen', 'usage': {'cost': 0.01}}}}
                return {'action': 'pass'}
        mapping = {'Model A': {'provider': 'a', 'model': 'qwen'}}
        job = {'seed': 900, 'reward': 'individual', 'visibility': 'unmentioned', 'assignment': {a: 'Model A' for a in ('A1','A2','A3','A4')}}
        with tempfile.TemporaryDirectory() as tmp, patch('swarm_lab.assistance.TeamPolicy', FakeTeam):
            out = Path(tmp)/'run'
            with self.assertRaisesRegex(RuntimeError, 'Readable reasoning missing'):
                run_one(job, mapping, out, False, {'Model A': {'provider': 'a', 'model': 'qwen'}})
            self.assertEqual(json.loads((out/'manifest.json').read_text())['status'], 'failed')
            self.assertEqual(json.loads((out/'usage.json').read_text())['reported_cost_usd'], 0.01)
            self.assertEqual(json.loads((out/'trajectory.jsonl').read_text())['type'], 'rejected')
            self.assertFalse((out/'metrics.json').exists())

    def test_every_successful_action_saves_readable_reasoning(self):
        class FakeTeam:
            def __init__(self, assignments): self.last_response = None
            def __call__(self, obs, rng):
                self.last_response = {'request': {'reasoning': {'enabled': True}}, 'response': {'message': {'reasoning_details': [{'type': 'reasoning.text', 'text': 'I will pass.'}]}, 'done_reason': 'stop', 'raw': {'provider': 'a', 'model': 'qwen', 'usage': {'cost': 0.01}}}}
                return {'action': 'pass'}
        mapping = {'Model A': {'provider': 'a', 'model': 'qwen'}}
        job = {'seed': 900, 'reward': 'individual', 'visibility': 'unmentioned', 'assignment': {a: 'Model A' for a in ('A1','A2','A3','A4')}}
        with tempfile.TemporaryDirectory() as tmp, patch('swarm_lab.assistance.TeamPolicy', FakeTeam):
            out = Path(tmp)/'run'
            run_one(job, mapping, out, False, {'Model A': {'provider': 'a', 'model': 'qwen'}})
            rows = [json.loads(line) for line in (out/'reasoning.jsonl').read_text().splitlines()]
            self.assertEqual(len(rows), 18)
            self.assertTrue(all(row['reasoning'] == 'I will pass.' for row in rows))
            verify(SimpleNamespace(run_dir=str(out)))

    def test_invalid_action_gets_one_logged_correction_without_changing_board(self):
        class FakeTeam:
            calls = 0
            def __init__(self, assignments): self.last_response = None
            def __call__(self, obs, rng):
                FakeTeam.calls += 1
                if FakeTeam.calls == 1:
                    action = {'action': 'resolve', 'task_id': 'NOT-AN-OPTION'}
                else:
                    if FakeTeam.calls == 2:
                        assert obs['action_correction']['previous_action']['task_id'] == 'NOT-AN-OPTION'
                    action = {'action': 'pass'}
                self.last_response = {'request': {'reasoning': {'enabled': True}}, 'response': {'message': {'reasoning': 'Choose an action.'}, 'done_reason': 'stop', 'raw': {'provider': 'a', 'model': 'qwen', 'usage': {'cost': 0.01}}}}
                return action
        mapping = {'Model A': {'provider': 'a', 'model': 'qwen'}}
        job = {'seed': 900, 'reward': 'individual', 'visibility': 'announced', 'assignment': {a: 'Model A' for a in ('A1','A2','A3','A4')}}
        with tempfile.TemporaryDirectory() as tmp, patch('swarm_lab.assistance.TeamPolicy', FakeTeam):
            out = Path(tmp)/'run'; FakeTeam.calls = 0
            run_one(job, mapping, out, False, {'Model A': {'provider': 'a', 'model': 'qwen'}})
            rows = [json.loads(line) for line in (out/'trajectory.jsonl').read_text().splitlines()]
            self.assertEqual(rows[0]['type'], 'invalid_attempt')
            self.assertEqual(rows[1]['type'], 'turn')
            self.assertEqual(rows[1]['event']['action'], {'action': 'pass'})
            self.assertEqual(FakeTeam.calls, 19)
            self.assertEqual(json.loads((out/'metrics.json').read_text())['invalid_first_attempts'], 1)
            self.assertEqual(json.loads((out/'usage.json').read_text())['calls'], 19)
            verify(SimpleNamespace(run_dir=str(out)))

    def test_second_invalid_action_fails_without_forcing_pass(self):
        class InvalidTeam:
            def __init__(self, assignments): self.last_response = None
            def __call__(self, obs, rng):
                self.last_response = {'request': {'reasoning': {'enabled': True}}, 'response': {'message': {'reasoning': 'Bad choice.'}, 'done_reason': 'stop', 'raw': {'provider': 'a', 'model': 'qwen', 'usage': {'cost': .01}}}}
                return {'action': 'resolve', 'task_id': 'INVALID'}
        mapping = {'Model A': {'provider': 'a', 'model': 'qwen'}}
        job = {'seed': 900, 'reward': 'individual', 'visibility': 'unmentioned', 'assignment': {a: 'Model A' for a in ('A1','A2','A3','A4')}}
        with tempfile.TemporaryDirectory() as tmp, patch('swarm_lab.assistance.TeamPolicy', InvalidTeam):
            out = Path(tmp)/'run'
            with self.assertRaisesRegex(RuntimeError, 'after one correction'):
                run_one(job, mapping, out, False, {'Model A': {'provider': 'a', 'model': 'qwen'}})
            self.assertEqual(json.loads((out/'usage.json').read_text())['calls'], 2)
            self.assertEqual([json.loads(line)['type'] for line in (out/'trajectory.jsonl').read_text().splitlines()], ['invalid_attempt','invalid_attempt'])

if __name__ == '__main__': unittest.main()
