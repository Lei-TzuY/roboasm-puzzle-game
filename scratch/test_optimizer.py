import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from optimizer import Optimizer

class TestOptimizer(unittest.TestCase):

    def test_constant_folding(self):
        insts = [
            {'opcode': 'MOV', 'args': [5, 'R0'], 'line_num': 1},
            {'opcode': 'ADD', 'args': [3, 'R0'], 'line_num': 2}
        ]
        opt = Optimizer(insts)
        res = opt.optimize()
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]['opcode'], 'MOV')
        self.assertEqual(res[0]['args'], [8, 'R0'])

    def test_remove_redundant_jumps(self):
        insts = [
            {'opcode': 'MOV', 'args': [1, 'R0'], 'line_num': 1},
            {'opcode': 'JMP', 'args': [2], 'line_num': 2},
            {'opcode': 'INC', 'args': ['R0'], 'line_num': 3}
        ]
        opt = Optimizer(insts)
        res = opt.optimize()
        self.assertEqual(len(res), 2)
        self.assertEqual(res[0]['opcode'], 'MOV')
        self.assertEqual(res[1]['opcode'], 'INC')

    def test_remove_dead_code(self):
        insts = [
            {'opcode': 'HLT', 'args': [], 'line_num': 1},
            {'opcode': 'MOVE', 'args': [], 'line_num': 2},
            {'opcode': 'PICK', 'args': [], 'line_num': 3}
        ]
        labels = {'start': 0}
        opt = Optimizer(insts, labels)
        res = opt.optimize()
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]['opcode'], 'HLT')

if __name__ == '__main__':
    unittest.main()
