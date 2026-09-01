import json
import os
import random
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from assembler import Assembler
from lexer import Lexer
from runtime_api import execute_level_code

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
LEVEL_PATH = os.path.join(ROOT_DIR, 'levels', 'level1.json')
NODE_RUNNER = os.path.join(ROOT_DIR, 'scratch', 'js_runtime_runner.js')
CASE_COUNT = 128
BASE_SEED = 0x5EED2026
CONTROL_FLOW = {'JMP', 'JEQ', 'JNE', 'JLT', 'JGT', 'CALL'}


def generate_program(seed):
    """Generate a bounded forward-only RoboASM CFG for optimizer fuzzing."""
    rng = random.Random(seed)
    lines = []

    # Deterministic initial register state keeps every later operand valid.
    for reg in range(4):
        lines.append(f'MOV {rng.randint(-8, 8)} R{reg}')

    branch_ops = ['JEQ', 'JNE', 'JLT', 'JGT']
    arithmetic_ops = ['ADD', 'SUB', 'MUL']

    for block in range(3):
        reg = f'R{rng.randrange(4)}'
        if rng.random() < 0.75:
            lines.append('NOP')

        # A common optimizer pattern: MOV immediate followed by arithmetic on
        # the same register. Values stay deliberately small for JS parity.
        base = rng.randint(-9, 9)
        delta = rng.randint(-4, 4)
        op = rng.choice(arithmetic_ops)
        lines.append(f'MOV {base} {reg}')
        lines.append(f'{op} {delta} {reg}')

        # Conditional target is always forward, guaranteeing bounded execution.
        target = f'cond_{block}'
        lines.append(f'CMP {reg} {rng.randint(-12, 12)}')
        lines.append(f'{rng.choice(branch_ops)} {target}')
        other = f'R{rng.randrange(4)}'
        lines.append(f'INC {other}')
        lines.append(f'{target}: NOP')

        # Exercise unreachable-code deletion and target remapping. The skipped
        # instruction is intentionally unlabeled so it is eligible for DCE.
        skip = f'skip_{block}'
        lines.append(f'JMP {skip}')
        lines.append(f'MOV {rng.randint(20, 40)} R{rng.randrange(4)}')
        lines.append(f'{skip}: DEC R{rng.randrange(4)}')

    # Roughly half of generated programs exercise CALL/RET compaction too.
    if rng.random() < 0.5:
        lines.extend([
            'CALL fuzz_fn',
            'JMP fuzz_done',
            f'MOV {rng.randint(50, 80)} R3',
            f'fuzz_fn: MOV {rng.randint(-5, 5)} R0',
            f'{rng.choice(arithmetic_ops)} {rng.randint(-3, 3)} R0',
            'RET',
            'fuzz_done: NOP',
        ])

    lines.append('HLT')
    return '\n'.join(lines) + '\n'


def semantic_projection(state):
    """Project away optimizer-dependent PC/cycle indexes, keep program state."""
    return {
        'halted': bool(state['halted']),
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
                'call_stack': list(robot['call_stack']),
                'halted': bool(robot['halted']),
            }
            for robot in state['robots']
        ],
        'ram': {str(key): value for key, value in state.get('ram', {}).items()},
        'messages': list(state.get('messages', [])),
        'grid': state.get('grid', {}),
        'faults': list(state.get('faults', [])),
    }


def web_semantic_projection(state):
    """Match the semantic projection produced by the Node runner snapshot."""
    return {
        'halted': bool(state['halted']),
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
                'call_stack': list(robot['call_stack']),
                'halted': bool(robot['halted']),
            }
            for robot in state['robots']
        ],
        'ram': {str(key): value for key, value in state.get('ram', {}).items()},
        'messages': list(state.get('messages', [])),
        'grid': state.get('grid', {}),
    }


def bytecode_projection(instructions):
    return [
        {'opcode': inst['opcode'], 'args': list(inst.get('args', []))}
        for inst in instructions
    ]


def generated_cases():
    return [
        {
            'name': f'fuzz-{index:03d}-seed-{BASE_SEED + index}',
            'seed': BASE_SEED + index,
            'level': 'level1.json',
            'code': generate_program(BASE_SEED + index),
            'max_cycles': 200,
            'optimize': True,
        }
        for index in range(CASE_COUNT)
    ]


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
    payload = json.loads(completed.stdout)
    return payload['results']


class TestOptimizerPropertyFuzz(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = generated_cases()
        cls.web_results = run_web(cls.cases)

    def test_optimization_preserves_terminal_semantics(self):
        for case in self.cases:
            with self.subTest(seed=case['seed']):
                plain = execute_level_code(
                    case['code'], LEVEL_PATH, max_cycles=case['max_cycles'],
                    optimize=False, source_base_dir=ROOT_DIR,
                )
                optimized = execute_level_code(
                    case['code'], LEVEL_PATH, max_cycles=case['max_cycles'],
                    optimize=True, source_base_dir=ROOT_DIR,
                )
                context = f"seed={case['seed']}\n{case['code']}"
                self.assertEqual(plain['won'], optimized['won'], context)
                self.assertEqual(
                    semantic_projection(plain['state']),
                    semantic_projection(optimized['state']),
                    context,
                )

    def test_optimized_control_flow_targets_are_in_range(self):
        for case in self.cases:
            with self.subTest(seed=case['seed']):
                assembler = Assembler(Lexer(case['code']).tokenize(), base_dir=ROOT_DIR)
                instructions = assembler.assemble(optimize=True)
                count = len(instructions)
                for inst in instructions:
                    if inst['opcode'] in CONTROL_FLOW:
                        target = inst['args'][0]
                        self.assertIsInstance(target, int, case['code'])
                        self.assertGreaterEqual(target, 0, case['code'])
                        self.assertLessEqual(target, count, case['code'])
                for label, value in assembler.labels.items():
                    self.assertGreaterEqual(value, 0, f'{label}\n{case["code"]}')
                    self.assertLessEqual(value, count, f'{label}\n{case["code"]}')

    def test_web_and_python_optimized_bytecode_match_for_generated_cfgs(self):
        self.assertEqual(len(self.web_results), len(self.cases))
        for case, web_result in zip(self.cases, self.web_results):
            with self.subTest(seed=case['seed']):
                context = f"seed={case['seed']}\n{case['code']}"
                self.assertEqual(web_result['status'], 'success', web_result.get('error', context))
                python_result = execute_level_code(
                    case['code'], LEVEL_PATH, max_cycles=case['max_cycles'],
                    optimize=True, source_base_dir=ROOT_DIR,
                )
                self.assertEqual(
                    web_result['bytecode'],
                    bytecode_projection(python_result['instructions']),
                    context,
                )
                self.assertEqual(web_result['won'], python_result['won'], context)
                self.assertEqual(web_result['cycles'], python_result['cycles'], context)
                self.assertEqual(
                    web_semantic_projection(web_result['state']),
                    {k: v for k, v in semantic_projection(python_result['state']).items() if k != 'faults'},
                    context,
                )


if __name__ == '__main__':
    unittest.main()
