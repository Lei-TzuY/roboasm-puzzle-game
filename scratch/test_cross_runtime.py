import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from runtime_api import execute_level_code

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
NODE_RUNNER = os.path.join(ROOT_DIR, 'scratch', 'js_runtime_runner.js')

# Keep this corpus intentionally representative rather than redundant. Each
# bundled case exercises a materially different part of the shared runtime.
DIFFERENTIAL_CASES = [
    ('movement-item-win', 1, 100),
    ('inbox-arithmetic-loop', 2, 200),
    ('multi-outbox-branching', 7, 200),
    ('stack-constants', 13, 150),
    ('bitwise-shifts', 14, 150),
    ('dual-robot-ipc', 15, 150),
    ('portal-transport', 16, 100),
    ('shared-ram-sort', 17, 300),
    ('data-matrix-map', 18, 100),
    ('button-door-portal-stack', 20, 200),
    ('linked-list-data', 21, 100),
    ('binary-search-data', 22, 250),
    ('four-robot-ipc', 24, 150),
    ('pcb-data', 25, 150),
    ('routing-data', 26, 150),
    ('paging-data', 27, 150),
    ('allocator-data', 31, 100),
    ('self-modifying-data', 33, 100),
    ('dual-robot-finale', 35, 150),
]

# These micro-programs pin language semantics that differ naturally between
# JavaScript and Python and therefore need explicit compatibility coverage.
INLINE_CASES = [
    {
        'name': 'noop-alias',
        'level_number': 1,
        'level': 'level1.json',
        'code': 'MOV 1 R0\nNOOP\nINC R0\nHLT\n',
        'max_cycles': 10,
        'optimize': False,
    },
    {
        'name': 'negative-modulo',
        'level_number': 1,
        'level': 'level1.json',
        'code': 'MOV -5 R0\nMOD 3 R0\nHLT\n',
        'max_cycles': 10,
        'optimize': False,
    },
    {
        'name': 'wide-bitwise',
        'level_number': 1,
        'level': 'level1.json',
        'code': (
            'MOV 1099511627776 R0\n'
            'OR 1 R0\n'
            'XOR 3 R0\n'
            'HLT\n'
        ),
        'max_cycles': 10,
        'optimize': False,
    },
    {
        'name': 'negative-shift-fault',
        'level_number': 1,
        'level': 'level1.json',
        'code': 'MOV 8 R0\nSHL R0 -1\nHLT\n',
        'max_cycles': 10,
        'optimize': False,
    },
]


def _coord_key(entry):
    return (entry['x'], entry['y'])


def normalize_snapshot(snapshot):
    """Project Python and JavaScript snapshots onto their shared semantics."""
    return {
        'cycles': snapshot['cycles'],
        'halted': bool(snapshot['halted']),
        'robots': [
            {
                'id': robot['id'],
                'x': robot['x'],
                'y': robot['y'],
                'facing': robot['facing'],
                'inventory': robot['inventory'],
                'registers': dict(robot['registers']),
                'flags': dict(robot['flags']),
                'stack': list(robot['stack']),
                'pc': robot['pc'],
                'call_stack': list(robot['call_stack']),
                'halted': bool(robot['halted']),
            }
            for robot in snapshot['robots']
        ],
        # JSON object keys are strings on the Node side, so normalize the Python
        # integer-addressed RAM dictionary to the same representation.
        'ram': {
            str(key): value
            for key, value in sorted(
                snapshot.get('ram', {}).items(),
                key=lambda item: int(item[0]),
            )
        },
        'messages': [
            {
                'sender_id': message['sender_id'],
                'value': message['value'],
            }
            for message in snapshot.get('messages', [])
        ],
        'grid': {
            'width': snapshot['grid']['width'],
            'height': snapshot['grid']['height'],
            'items': sorted(snapshot['grid'].get('items', []), key=_coord_key),
            'inboxes': sorted(snapshot['grid'].get('inboxes', []), key=_coord_key),
            'outboxes': sorted(snapshot['grid'].get('outboxes', []), key=_coord_key),
            'open_doors': sorted(
                snapshot['grid'].get('open_doors', []),
                key=_coord_key,
            ),
        },
    }


def load_cases():
    cases = []
    for name, level_number, max_cycles in DIFFERENTIAL_CASES:
        solution_path = os.path.join(
            ROOT_DIR,
            'solutions',
            f'level{level_number}.asm',
        )
        with open(solution_path, 'r', encoding='utf-8') as handle:
            code = handle.read()
        cases.append({
            'name': name,
            'level_number': level_number,
            'level': f'level{level_number}.json',
            'code': code,
            'max_cycles': max_cycles,
            'optimize': False,
        })
    cases.extend(dict(case) for case in INLINE_CASES)
    return cases


def run_web_cases(cases):
    completed = subprocess.run(
        ['node', NODE_RUNNER],
        input=json.dumps({'cases': cases}),
        text=True,
        capture_output=True,
        cwd=ROOT_DIR,
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(
            'Embedded Web VM runner failed.\n'
            f'stdout:\n{completed.stdout}\n'
            f'stderr:\n{completed.stderr}'
        )
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise AssertionError(
            f'Web VM runner returned invalid JSON: {completed.stdout!r}'
        ) from exc
    return payload['results']


class TestCrossRuntimeDifferential(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = load_cases()
        cls.web_results = run_web_cases(cls.cases)

    def test_embedded_web_vm_matches_python_cycle_by_cycle(self):
        self.assertEqual(len(self.web_results), len(self.cases))

        for case, web_result in zip(self.cases, self.web_results):
            with self.subTest(case=case['name']):
                self.assertEqual(
                    web_result['status'],
                    'success',
                    web_result.get(
                        'error',
                        'Web runtime failed without an error message',
                    ),
                )

                level_path = os.path.join(ROOT_DIR, 'levels', case['level'])
                python_result = execute_level_code(
                    case['code'],
                    level_path,
                    max_cycles=case['max_cycles'],
                    capture_trace=True,
                    optimize=case['optimize'],
                    source_base_dir=ROOT_DIR,
                )

                self.assertEqual(web_result['won'], python_result['won'])
                self.assertEqual(web_result['cycles'], python_result['cycles'])
                self.assertEqual(web_result['size'], python_result['size'])
                self.assertEqual(
                    len(web_result['trace']),
                    len(python_result['execution']['trace']),
                    'Trace lengths diverged',
                )

                for cycle, (web_snapshot, python_snapshot) in enumerate(zip(
                    web_result['trace'],
                    python_result['execution']['trace'],
                )):
                    self.assertEqual(
                        normalize_snapshot(web_snapshot),
                        normalize_snapshot(python_snapshot),
                        f"Runtime drift in {case['name']} at cycle {cycle}",
                    )

                self.assertEqual(
                    normalize_snapshot(web_result['state']),
                    normalize_snapshot(python_result['state']),
                    f"Terminal state drift in {case['name']}",
                )


if __name__ == '__main__':
    unittest.main()
