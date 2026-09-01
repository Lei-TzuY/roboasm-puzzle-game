import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from runtime_api import execute_level_code

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
NODE_RUNNER = os.path.join(ROOT_DIR, 'scratch', 'js_runtime_runner.js')
LEVEL_CASES = [1, 2, 7, 13, 17, 20, 22, 24, 35]

MICRO_CASES = [
    ('target-remap', 'JMP target\nNOP\ntarget: MOV 5 R0\nADD 3 R0\nHLT\n'),
    ('secondary-entry', 'JMP add_only\nMOV 5 R0\nadd_only: ADD 3 R0\nHLT\n'),
    ('call-remap', 'CALL fn\nHLT\nNOP\nfn: MOV 2 R0\nADD 3 R0\nRET\n'),
    ('dead-block', 'JMP 3\nMOV 99 R0\nNOP\nMOV 5 R0\nHLT\n'),
]


def bytecode_projection(instructions):
    return [
        {'opcode': inst['opcode'], 'args': list(inst.get('args', []))}
        for inst in instructions
    ]


def normalize_terminal(state):
    return {
        'cycles': state['cycles'],
        'halted': bool(state['halted']),
        'robots': [
            {
                'id': robot['id'], 'x': robot['x'], 'y': robot['y'],
                'facing': robot['facing'], 'inventory': robot['inventory'],
                'registers': dict(robot['registers']), 'pc': robot['pc'],
                'halted': bool(robot['halted']),
            }
            for robot in state['robots']
        ],
        'ram': {str(k): v for k, v in state.get('ram', {}).items()},
    }


def load_cases():
    cases = []
    for level_number in LEVEL_CASES:
        with open(os.path.join(ROOT_DIR, 'solutions', f'level{level_number}.asm'), encoding='utf-8') as handle:
            code = handle.read()
        cases.append({
            'name': f'level-{level_number}-optimized',
            'level': f'level{level_number}.json',
            'code': code,
            'max_cycles': 500,
            'optimize': True,
        })
    for name, code in MICRO_CASES:
        cases.append({
            'name': name,
            'level': 'level1.json',
            'code': code,
            'max_cycles': 50,
            'optimize': True,
        })
    return cases


def run_web(cases):
    completed = subprocess.run(
        ['node', NODE_RUNNER],
        input=json.dumps({'cases': cases}),
        text=True,
        capture_output=True,
        cwd=ROOT_DIR,
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(completed.stderr or completed.stdout)
    return json.loads(completed.stdout)['results']


class TestOptimizerParity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = load_cases()
        cls.web_results = run_web(cls.cases)

    def test_optimized_bytecode_and_terminal_state_match_python(self):
        for case, web_result in zip(self.cases, self.web_results):
            with self.subTest(case=case['name']):
                self.assertEqual(web_result['status'], 'success', web_result.get('error'))
                python_result = execute_level_code(
                    case['code'],
                    os.path.join(ROOT_DIR, 'levels', case['level']),
                    max_cycles=case['max_cycles'],
                    optimize=True,
                    source_base_dir=ROOT_DIR,
                )
                self.assertEqual(
                    web_result['bytecode'],
                    bytecode_projection(python_result['instructions']),
                    f"optimized bytecode drift: {case['name']}",
                )
                self.assertEqual(web_result['won'], python_result['won'])
                self.assertEqual(web_result['cycles'], python_result['cycles'])
                self.assertEqual(
                    normalize_terminal(web_result['state']),
                    normalize_terminal(python_result['state']),
                    f"optimized terminal-state drift: {case['name']}",
                )


if __name__ == '__main__':
    unittest.main()
