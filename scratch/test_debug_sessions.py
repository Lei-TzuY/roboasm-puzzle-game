import json
import os
import sys
import threading
import unittest
import urllib.error
import urllib.request
from http.server import HTTPServer

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from debug_sessions import (
    DebugSession,
    DebugSessionManager,
    DebugSessionNotFound,
    MAX_DEBUG_STEP_CYCLES,
)
from runtime_api import execute_level_code
from web_server import RoboASMRequestHandler

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
LEVEL_PATH = os.path.join(ROOT_DIR, 'levels', 'level1.json')
SOLUTION_PATH = os.path.join(ROOT_DIR, 'solutions', 'level1.asm')


def load_solution():
    with open(SOLUTION_PATH, 'r', encoding='utf-8') as handle:
        return handle.read()


class TestDebugSession(unittest.TestCase):
    def test_step_then_run_reuses_same_authoritative_vm(self):
        code = load_solution()
        session = DebugSession(
            code,
            LEVEL_PATH,
            source_base_dir=ROOT_DIR,
        )
        self.assertEqual(session.snapshot()['cycles'], 0)

        stepped = session.step(2)
        self.assertEqual(stepped['execution']['cycles_executed'], 2)
        self.assertEqual(stepped['cycles'], 2)
        self.assertFalse(stepped['won'])

        finished = session.run(max_cycles=200)
        one_shot = execute_level_code(
            code,
            LEVEL_PATH,
            max_cycles=200,
            source_base_dir=ROOT_DIR,
        )
        self.assertTrue(finished['won'])
        self.assertEqual(finished['cycles'], one_shot['cycles'])
        self.assertEqual(finished['state'], one_shot['state'])

    def test_terminal_session_does_not_advance_again(self):
        session = DebugSession(
            load_solution(),
            LEVEL_PATH,
            source_base_dir=ROOT_DIR,
        )
        finished = session.run(max_cycles=200)
        cycles = finished['cycles']
        again = session.step()

        self.assertTrue(again['terminal'])
        self.assertEqual(again['cycles'], cycles)
        self.assertEqual(again['execution']['cycles_executed'], 0)

    def test_incremental_trace_starts_from_current_cycle(self):
        session = DebugSession(
            load_solution(),
            LEVEL_PATH,
            source_base_dir=ROOT_DIR,
        )
        session.step(2)
        result = session.run(max_cycles=2, capture_trace=True)

        trace = result['execution']['trace']
        self.assertEqual(trace[0]['cycles'], 2)
        self.assertEqual(trace[-1]['cycles'], result['cycles'])
        self.assertLessEqual(result['execution']['cycles_executed'], 2)

    def test_step_budget_validation(self):
        session = DebugSession('HLT', LEVEL_PATH, source_base_dir=ROOT_DIR)
        for invalid in (0, MAX_DEBUG_STEP_CYCLES + 1, True, '1'):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    session.step(invalid)


class TestDebugSessionManager(unittest.TestCase):
    def test_capacity_uses_lru_eviction(self):
        now = [0.0]
        tokens = iter(['session-a', 'session-b', 'session-c'])
        manager = DebugSessionManager(
            max_sessions=2,
            ttl_seconds=100,
            clock=lambda: now[0],
            token_factory=lambda: next(tokens),
        )

        first_id, first = manager.create(
            'HLT', LEVEL_PATH, source_base_dir=ROOT_DIR
        )
        second_id, _ = manager.create(
            'HLT', LEVEL_PATH, source_base_dir=ROOT_DIR
        )
        self.assertIs(manager.get(first_id), first)
        third_id, _ = manager.create(
            'HLT', LEVEL_PATH, source_base_dir=ROOT_DIR
        )

        self.assertEqual(manager.active_count(), 2)
        self.assertIs(manager.get(first_id), first)
        self.assertIsNotNone(manager.get(third_id))
        with self.assertRaises(DebugSessionNotFound):
            manager.get(second_id)

    def test_ttl_is_refreshed_on_access_and_then_expires(self):
        now = [0.0]
        manager = DebugSessionManager(
            max_sessions=2,
            ttl_seconds=10,
            clock=lambda: now[0],
            token_factory=lambda: 'ttl-session',
        )
        session_id, session = manager.create(
            'HLT', LEVEL_PATH, source_base_dir=ROOT_DIR
        )

        now[0] = 6.0
        self.assertIs(manager.get(session_id), session)
        now[0] = 15.0
        self.assertIs(manager.get(session_id), session)
        now[0] = 26.0
        with self.assertRaises(DebugSessionNotFound):
            manager.get(session_id)
        self.assertEqual(manager.active_count(), 0)


class TestDebugSessionHTTPAPI(unittest.TestCase):
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
        self.assertEqual(payload['cycles'], 0)
        return payload['session_id']

    def test_http_session_persists_state_across_step_run_get_delete(self):
        session_id = self.create_session()

        step_status, stepped = self.request_json(
            'POST', f'/api/debug/sessions/{session_id}/step', {'cycles': 2}
        )
        self.assertEqual(step_status, 200)
        self.assertEqual(stepped['cycles'], 2)
        self.assertEqual(stepped['execution']['cycles_executed'], 2)

        get_status, current = self.request_json(
            'GET', f'/api/debug/sessions/{session_id}'
        )
        self.assertEqual(get_status, 200)
        self.assertEqual(current['cycles'], 2)

        run_status, finished = self.request_json(
            'POST', f'/api/debug/sessions/{session_id}/run',
            {'max_cycles': 200},
        )
        self.assertEqual(run_status, 200)
        self.assertTrue(finished['won'])
        self.assertEqual(finished['cycles'], 8)

        delete_status, deleted = self.request_json(
            'DELETE', f'/api/debug/sessions/{session_id}'
        )
        self.assertEqual(delete_status, 200)
        self.assertTrue(deleted['deleted'])

        missing_status, missing = self.request_json(
            'GET', f'/api/debug/sessions/{session_id}'
        )
        self.assertEqual(missing_status, 404)
        self.assertIn('not found', missing['error'].lower())

    def test_http_session_returns_structured_compile_error(self):
        status, payload = self.request_json('POST', '/api/debug/sessions', {
            'level': 'level1.json',
            'code': 'MOV 1 X',
        })
        self.assertEqual(status, 400)
        self.assertEqual(payload['line_num'], 1)
        self.assertIn('must be writable', payload['error'])

    def test_http_session_rejects_bad_incremental_budgets(self):
        session_id = self.create_session()
        try:
            status, payload = self.request_json(
                'POST', f'/api/debug/sessions/{session_id}/step', {'cycles': 0}
            )
            self.assertEqual(status, 400)
            self.assertIn('cycles must be between', payload['error'])

            status, payload = self.request_json(
                'POST', f'/api/debug/sessions/{session_id}/run',
                {'max_cycles': '100'},
            )
            self.assertEqual(status, 400)
            self.assertIn('max_cycles must be an integer', payload['error'])
        finally:
            self.request_json('DELETE', f'/api/debug/sessions/{session_id}')


if __name__ == '__main__':
    unittest.main()
