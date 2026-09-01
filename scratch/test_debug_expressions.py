import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from debug_expressions import (
    DebugExpressionError,
    compile_debug_expression,
    evaluate_debug_expression,
)


class TestDebugExpressions(unittest.TestCase):
    def test_safe_state_expression_evaluates_without_python_eval(self):
        compiled = compile_debug_expression(
            'R0 == 4 and RAM[0] == 7 and ZERO is False and INV is None'
        )
        context = {
            'R0': 4, 'R1': 0, 'R2': 0, 'R3': 0,
            'INV': None, 'X': 1, 'Y': 2, 'PC': 3, 'CYCLES': 4,
            'ZERO': False, 'NEGATIVE': False, 'RAM': {0: 7},
        }
        self.assertTrue(evaluate_debug_expression(compiled, context))

    def test_unsafe_or_unbounded_expressions_are_rejected(self):
        invalid = [
            '__import__("os")',
            'R0.__class__',
            '[R0][0]',
            'open(1)',
            '"text" == "text"',
            '1 << 20',
            str(1 << 80),
            'RAM[9223372036854775808] == 1',
        ]
        for source in invalid:
            with self.subTest(source=source):
                with self.assertRaises(DebugExpressionError):
                    compile_debug_expression(source)

    def test_runtime_expression_errors_are_structured(self):
        compiled = compile_debug_expression('R0 // 0 == 1')
        context = {
            'R0': 4, 'R1': 0, 'R2': 0, 'R3': 0,
            'INV': None, 'X': 0, 'Y': 0, 'PC': 0, 'CYCLES': 0,
            'ZERO': False, 'NEGATIVE': False, 'RAM': {},
        }
        with self.assertRaisesRegex(
            DebugExpressionError,
            'Conditional breakpoint evaluation failed',
        ):
            evaluate_debug_expression(compiled, context)


if __name__ == '__main__':
    unittest.main()
