import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from assembler import Assembler
from lexer import Lexer
from optimizer import Optimizer


class TestControlFlowSafeOptimizer(unittest.TestCase):
    def test_nop_removal_can_expose_and_remove_redundant_jump(self):
        insts = [
            {'opcode': 'JMP', 'args': [2], 'line_num': 1},
            {'opcode': 'NOP', 'args': [], 'line_num': 2},
            {'opcode': 'HLT', 'args': [], 'line_num': 3},
        ]
        result = Optimizer(insts).optimize()
        self.assertEqual(result, [
            {'opcode': 'HLT', 'args': [], 'line_num': 3},
        ])

    def test_constant_fold_does_not_cross_secondary_entry(self):
        insts = [
            {'opcode': 'JMP', 'args': [2], 'line_num': 1},
            {'opcode': 'MOV', 'args': [5, 'R0'], 'line_num': 2},
            {'opcode': 'ADD', 'args': [3, 'R0'], 'line_num': 3},
            {'opcode': 'HLT', 'args': [], 'line_num': 4},
        ]
        result = Optimizer(insts).optimize()

        # The MOV is unreachable and may disappear, and its JMP may then become
        # redundant. The important invariant is that the targeted ADD must not
        # be folded with the unreachable MOV into MOV 8 R0.
        self.assertEqual(result, [
            {'opcode': 'ADD', 'args': [3, 'R0'], 'line_num': 3},
            {'opcode': 'HLT', 'args': [], 'line_num': 4},
        ])

    def test_constant_folding_reaches_fixed_point_in_one_optimize_call(self):
        insts = [
            {'opcode': 'MOV', 'args': [1, 'R0'], 'line_num': 1},
            {'opcode': 'ADD', 'args': [2, 'R0'], 'line_num': 2},
            {'opcode': 'ADD', 'args': [3, 'R0'], 'line_num': 3},
            {'opcode': 'MUL', 'args': [4, 'R0'], 'line_num': 4},
            {'opcode': 'HLT', 'args': [], 'line_num': 5},
        ]
        optimizer = Optimizer(insts)
        once = optimizer.optimize()
        twice_optimizer = Optimizer(once, optimizer.labels)
        twice = twice_optimizer.optimize()

        self.assertEqual(once, [
            {'opcode': 'MOV', 'args': [24, 'R0'], 'line_num': 1},
            {'opcode': 'HLT', 'args': [], 'line_num': 5},
        ])
        self.assertEqual(once, twice)
        self.assertEqual(optimizer.labels, twice_optimizer.labels)

    def test_call_target_is_remapped_after_compaction(self):
        insts = [
            {'opcode': 'CALL', 'args': [3], 'line_num': 1},
            {'opcode': 'HLT', 'args': [], 'line_num': 2},
            {'opcode': 'NOP', 'args': [], 'line_num': 3},
            {'opcode': 'MOV', 'args': [2, 'R0'], 'line_num': 4},
            {'opcode': 'ADD', 'args': [3, 'R0'], 'line_num': 5},
            {'opcode': 'RET', 'args': [], 'line_num': 6},
        ]
        result = Optimizer(insts, {'fn': 3}).optimize()
        self.assertEqual(result[0]['opcode'], 'CALL')
        self.assertEqual(result[0]['args'], [2])
        self.assertEqual(result[2]['args'], [5, 'R0'])

    def test_assembler_optimized_targets_stay_in_range(self):
        code = 'JMP target\nNOP\nMOV 99 R0\ntarget: MOV 5 R0\nADD 3 R0\nHLT\n'
        assembler = Assembler(Lexer(code).tokenize())
        instructions = assembler.assemble(optimize=True)
        count = len(instructions)
        for inst in instructions:
            if inst['opcode'] in {'JMP', 'JEQ', 'JNE', 'JLT', 'JGT', 'CALL'}:
                self.assertGreaterEqual(inst['args'][0], 0)
                self.assertLessEqual(inst['args'][0], count)

    def test_optimized_symbol_table_tracks_remapped_label(self):
        code = 'NOP\nstart: MOV 5 R0\nADD 3 R0\nHLT\n'
        assembler = Assembler(Lexer(code).tokenize())
        instructions = assembler.assemble(optimize=True)
        self.assertEqual(instructions[0]['args'], [8, 'R0'])
        self.assertEqual(assembler.labels['start'], 0)
        self.assertEqual(assembler.symbol_table['start']['value'], 0)

    def test_trailing_exit_target_can_collapse_to_empty_program(self):
        code = 'NOP\nJMP done\nMOV 7 R0\ndone:\n'
        assembler = Assembler(Lexer(code).tokenize())
        instructions = assembler.assemble(optimize=True)

        # Jumping to EOF is equivalent to immediate program completion. Once
        # dead code and the newly redundant exit jump are removed, the named
        # EOF label must still point at the new program end (index zero).
        self.assertEqual(instructions, [])
        self.assertEqual(assembler.labels['done'], 0)
        self.assertEqual(assembler.symbol_table['done']['value'], 0)


if __name__ == '__main__':
    unittest.main()
