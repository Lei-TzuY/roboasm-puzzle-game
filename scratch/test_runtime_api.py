import json
import os
import sys
import threading
import unittest
import urllib.error
import urllib.request
from http.server import HTTPServer

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from runtime_api import MAX_RUN_CYCLES, MAX_TRACE_CYCLES, execute_level_code
from web_server import RoboASMRequestHandler, resolve_level_path

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


class TestHeadlessRuntime(unittest.TestCase):
    def test_bundled_solution_executes_through_python_runtime(self):
        level_path = os.path.join(ROOT_DIR, 'levels', 'level1.json')
        solution_path = os.path.join(ROOT_DIR, 'solutions', 'level1.asm')
        with open(solution_path, 'r', encoding='utf-8') as f:
            code = f.read()

        result = execute_level_code(code, level_path, max_cycles=200)

        self.assertEqual(result['status'], 'success')
        self.assertTrue(result['won'])
        self.assertGreater(result['cycles'], 0)
        self.assertEqual(result['cycles'], result['execution']['total_cycles'])
        self.assertEqual(result['state']['cycles'], result['cycles'])
        json.dumps(result)

    def test_trace_is_exposed_by_headless_runtime(self):
        level_path = os.path.join(ROOT_DIR, 'levels', 'level1.json')
        result = execute_level_code(
            'HLT',
            level_path,
            max_cycles=2,
            capture_trace=True,
        )

        self.assertIn('trace', result['execution'])
        self.assertGreaterEqual(len(result['execution']['trace']), 1)
        self.assertEqual(result['execution']['trace'][0]['cycles'], 0)

    def test_execution_limits_are_enforced(self):
        level_path = os.path.join(ROOT_DIR, 'levels', 'level1.json')
        with self.assertRaises(ValueError):
            execute_level_code('HLT', level_path, max_cycles=MAX_RUN_CYCLES + 1)
        with self.assertRaises(ValueError):
            execute_level_code(
                'HLT',
                level_path,
                max_cycles=MAX_TRACE_CYCLES + 1,
                capture_trace=True,
            )

    def test_level_resolver_is_confined_to_bundled_json_levels(self):
        resolved = resolve_level_path('../level1.json')
        self.assertEqual(os.path.basename(resolved), 'level1.json')
        self.assertTrue(resolved.startswith(os.path.join(ROOT_DIR, 'levels')))

        with self.assertRaises(ValueError):
            resolve_level_path('level1.asm')
        with self.assertRaises(FileNotFoundError):
            resolve_level_path('missing-level.json')


class TestRunHTTPAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(('127.0.0.1', 0), RoboASMRequestHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def get_raw(self, path):
        with urllib.request.urlopen(self.base_url + path, timeout=5) as response:
            return (
                response.status,
                response.headers.get_content_type(),
                response.read(),
            )

    def post_json(self, path, payload):
        request = urllib.request.Request(
            self.base_url + path,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode('utf-8'))

    def test_web_ui_injects_authoritative_runtime_bridge(self):
        status, content_type, body = self.get_raw('/')
        html = body.decode('utf-8')

        self.assertEqual(status, 200)
        self.assertEqual(content_type, 'text/html')
        self.assertEqual(html.count('<script src="/web_authority.js"></script>'), 1)
        self.assertIn('Visual Assembly IDE', html)

    def test_authority_bridge_asset_is_served_as_javascript(self):
        status, content_type, body = self.get_raw('/web_authority.js')
        source = body.decode('utf-8')

        self.assertEqual(status, 200)
        self.assertEqual(content_type, 'application/javascript')
        self.assertIn('Server Verify', source)
        self.assertIn("fetch('/api/run'", source)
        self.assertIn('Runtime drift detected', source)
        self.assertIn('capture_trace', source)

    def test_run_endpoint_executes_bundled_solution(self):
        solution_path = os.path.join(ROOT_DIR, 'solutions', 'level1.asm')
        with open(solution_path, 'r', encoding='utf-8') as f:
            code = f.read()

        status, payload = self.post_json('/api/run', {
            'level': 'level1.json',
            'code': code,
            'max_cycles': 200,
        })

        self.assertEqual(status, 200)
        self.assertTrue(payload['won'])
        self.assertEqual(payload['status'], 'success')
        self.assertIn('state', payload)

    def test_run_endpoint_returns_trace_for_debugger_bridge(self):
        status, payload = self.post_json('/api/run', {
            'level': 'level1.json',
            'code': 'HLT',
            'max_cycles': 2,
            'capture_trace': True,
        })

        self.assertEqual(status, 200)
        trace = payload['execution']['trace']
        self.assertGreaterEqual(len(trace), 1)
        self.assertEqual(trace[0]['cycles'], 0)
        self.assertIn('robots', trace[0])
        self.assertIn('grid', trace[0])

    def test_run_endpoint_returns_structured_compile_error(self):
        status, payload = self.post_json('/api/run', {
            'level': 'level1.json',
            'code': 'MOV 1 X',
        })

        self.assertEqual(status, 400)
        self.assertEqual(payload['status'], 'error')
        self.assertEqual(payload['line_num'], 1)
        self.assertIn('must be writable', payload['error'])

    def test_run_endpoint_rejects_unbounded_request(self):
        status, payload = self.post_json('/api/run', {
            'level': 'level1.json',
            'code': 'HLT',
            'max_cycles': MAX_RUN_CYCLES + 1,
        })

        self.assertEqual(status, 400)
        self.assertEqual(payload['status'], 'error')
        self.assertIn('max_cycles', payload['error'])


if __name__ == '__main__':
    unittest.main()
