import json
import os
import sys
import threading
import unittest
import urllib.error
import urllib.request
from http.server import HTTPServer

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from debug_expressions import DebugExpressionError, compile_debug_expression
from debug_sessions import DebugSession
from web_server import RoboASMRequestHandler

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
LEVEL_PATH = os.path.join(ROOT_DIR, 'levels', 'level1.json')
SOLUTION_PATH = os.path.join(ROOT_DIR, 'solutions', 'level1.asm')


def load_solution():
    with open(SOLUTION_PATH, 'r', encoding='utf-8') as handle:
        return handle.read()


class TestBreakpointAwareDebugRun(unittest.TestCase):
    def test_run_stops_before_selected_source_line_and_manual_step_crosses_it(self):
        session = DebugSession(
            load_solution(),
            LEVEL_PATH,
            source_base_dir=ROOT_DIR,
        )

        stopped = session.run(
            max_cycles=50,
            breakpoint_lines=[5],
            breakpoint_robot_id=0,
        )
        self.assertFalse(stopped['terminal'])
        self.assertEqual(stopped['cycles'], 2)
        self.assertEqual(stopped['history_depth'], 2)
        self.assertEqual(stopped['execution']['cycles_executed'], 2)
        self.assertTrue(stopped['execution']['stopped_by_breakpoint'])
        self.assertFalse(stopped['execution']['limit_reached'])
        self.assertEqual(stopped['execution']['breakpoint'], {
            'kind': 'line',
            'robot_id': 0,
            'pc': 2,
            'line_num': 5,
            'cycle': 2,
        })

        crossed = session.step(1)
        self.assertEqual(crossed['cycles'], 3)
        self.assertFalse(crossed['terminal'])
        self.assertEqual(crossed['state']['robots'][0]['pc'], 3)

        finished = session.run(
            max_cycles=50,
            breakpoint_lines=[5],
            breakpoint_robot_id=0,
        )
        self.assertTrue(finished['won'])
        self.assertEqual(finished['cycles'], 8)
        self.assertFalse(finished['execution']['stopped_by_breakpoint'])

    def test_cycle_zero_breakpoint_is_ignored_like_existing_web_run_semantics(self):
        session = DebugSession(
            load_solution(),
            LEVEL_PATH,
            source_base_dir=ROOT_DIR,
        )
        result = session.run(
            max_cycles=1,
            breakpoint_lines=[3],
            breakpoint_robot_id=0,
        )
        self.assertEqual(result['cycles'], 1)
        self.assertEqual(result['execution']['cycles_executed'], 1)
        self.assertFalse(result['execution']['stopped_by_breakpoint'])
        self.assertTrue(result['execution']['limit_reached'])

    def test_conditional_breakpoint_uses_safe_authoritative_state(self):
        session = DebugSession(
            'MOV 1 R0\nINC R0\nINC R0\nHLT',
            LEVEL_PATH,
            source_base_dir=ROOT_DIR,
        )
        stopped = session.run(
            max_cycles=20,
            conditional_breakpoints=[{
                'line_num': 3,
                'condition': 'R0 == 2 and PC == 2 and CYCLES == 2',
                'robot_id': 0,
            }],
        )
        self.assertEqual(stopped['cycles'], 2)
        self.assertFalse(stopped['terminal'])
        self.assertTrue(stopped['execution']['stopped_by_breakpoint'])
        hit = stopped['execution']['breakpoint']
        self.assertEqual(hit['kind'], 'conditional')
        self.assertEqual(hit['line_num'], 3)
        self.assertEqual(hit['condition'], 'R0 == 2 and PC == 2 and CYCLES == 2')
        self.assertEqual(stopped['state']['robots'][0]['registers']['R0'], 2)

        crossed = session.step(1)
        self.assertEqual(crossed['cycles'], 3)
        self.assertEqual(crossed['state']['robots'][0]['registers']['R0'], 3)

    def test_register_and_ram_watchpoints_stop_after_mutation_and_rewind(self):
        register_session = DebugSession(
            'MOV 4 R0\nHLT',
            LEVEL_PATH,
            source_base_dir=ROOT_DIR,
        )
        changed = register_session.run(
            max_cycles=10,
            watchpoints=[{'kind': 'register', 'robot_id': 0, 'name': 'R0'}],
        )
        self.assertEqual(changed['cycles'], 1)
        self.assertTrue(changed['execution']['stopped_by_watchpoint'])
        self.assertEqual(changed['execution']['watchpoint'], {
            'kind': 'register',
            'robot_id': 0,
            'name': 'R0',
            'old_exists': True,
            'old_value': 0,
            'new_exists': True,
            'new_value': 4,
            'cycle': 1,
        })

        ram_session = DebugSession(
            'MOV 0 R0\nMOV 7 R1\nSTORE R1 R0\nHLT',
            LEVEL_PATH,
            source_base_dir=ROOT_DIR,
        )
        stored = ram_session.run(
            max_cycles=10,
            watchpoints=[{'kind': 'ram', 'address': 0}],
        )
        self.assertEqual(stored['cycles'], 3)
        self.assertTrue(stored['execution']['stopped_by_watchpoint'])
        hit = stored['execution']['watchpoint']
        self.assertEqual(hit['kind'], 'ram')
        self.assertEqual(hit['address'], 0)
        self.assertFalse(hit['old_exists'])
        self.assertIsNone(hit['old_value'])
        self.assertTrue(hit['new_exists'])
        self.assertEqual(hit['new_value'], 7)
        self.assertEqual(stored['state']['ram'][0], 7)

        backed = ram_session.step(-1)
        self.assertEqual(backed['cycles'], 2)
        self.assertNotIn(0, backed['state']['ram'])

    def test_debug_conditions_reject_code_execution_and_invalid_watchpoints(self):
        for source in (
            '__import__("os")',
            'R0.__class__',
            '[R0][0]',
            'open(1)',
            '"text" == "text"',
        ):
            with self.subTest(source=source):
                with self.assertRaises(DebugExpressionError):
                    compile_debug_expression(source)

        session = DebugSession('NOP\nHLT', LEVEL_PATH, source_base_dir=ROOT_DIR)
        invalid_runs = [
            {'conditional_breakpoints': 'bad'},
            {'conditional_breakpoints': [{'line_num': 1, 'condition': 'R9 == 1'}]},
            {'conditional_breakpoints': [{'line_num': 0, 'condition': 'R0 == 1'}]},
            {'watchpoints': 'R0'},
            {'watchpoints': [{'kind': 'register', 'name': 'R9'}]},
            {'watchpoints': [{'kind': 'ram', 'address': True}]},
            {'watchpoints': [{'kind': 'unknown'}]},
        ]
        for kwargs in invalid_runs:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    session.run(max_cycles=1, **kwargs)

    def test_breakpoint_validation_rejects_ambiguous_or_invalid_inputs(self):
        session = DebugSession('NOP\nHLT', LEVEL_PATH, source_base_dir=ROOT_DIR)
        invalid_cases = [
            {'breakpoint_lines': '2'},
            {'breakpoint_lines': [0]},
            {'breakpoint_lines': [True]},
            {'breakpoint_lines': [1.5]},
            {'breakpoint_robot_id': True},
            {'breakpoint_robot_id': 1},
        ]
        for kwargs in invalid_cases:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    session.run(max_cycles=1, **kwargs)


class TestBreakpointAwareHTTPRun(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(('127.0.0.1', 0), RoboASMRequestHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def request_json(self, method, path, payload=None):
        data = None
        headers = {}
        if payload is not None:
            data = json.dumps(payload).encode('utf-8')
            headers['Content-Type'] = 'application/json'
        request = urllib.request.Request(
            self.base_url + path,
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode('utf-8')
            return exc.code, json.loads(body) if body else {}

    def create_session(self):
        status, payload = self.request_json('POST', '/api/debug/sessions', {
            'level': 'level1.json',
            'code': load_solution(),
            'optimize': False,
        })
        self.assertEqual(status, 201)
        return payload['session_id']

    def test_http_run_stops_at_breakpoint_and_preserves_rewind_history(self):
        session_id = self.create_session()
        try:
            status, stopped = self.request_json(
                'POST',
                f'/api/debug/sessions/{session_id}/run',
                {
                    'max_cycles': 32,
                    'breakpoint_lines': [5],
                    'breakpoint_robot_id': 0,
                },
            )
            self.assertEqual(status, 200)
            self.assertEqual(stopped['cycles'], 2)
            self.assertEqual(stopped['history_depth'], 2)
            self.assertTrue(stopped['execution']['stopped_by_breakpoint'])
            self.assertEqual(stopped['execution']['breakpoint']['line_num'], 5)

            back_status, backed = self.request_json(
                'POST',
                f'/api/debug/sessions/{session_id}/step',
                {'cycles': -1},
            )
            self.assertEqual(back_status, 200)
            self.assertEqual(backed['cycles'], 1)
            self.assertEqual(backed['history_depth'], 1)
        finally:
            self.request_json('DELETE', f'/api/debug/sessions/{session_id}')

    def test_http_run_rejects_bad_breakpoint_payload(self):
        session_id = self.create_session()
        try:
            status, payload = self.request_json(
                'POST',
                f'/api/debug/sessions/{session_id}/run',
                {'max_cycles': 4, 'breakpoint_lines': [0]},
            )
            self.assertEqual(status, 400)
            self.assertIn('breakpoint_lines', payload['error'])
        finally:
            self.request_json('DELETE', f'/api/debug/sessions/{session_id}')


if __name__ == '__main__':
    unittest.main()
