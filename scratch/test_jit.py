import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from jit_compiler import JITCompiler
from vm import Robot

class MockVMContext:
    def __init__(self, insts):
        self.instructions = insts
        self.msg_queue = []

class TestJITCompiler(unittest.TestCase):

    def test_jit_arithmetic_loop(self):
        insts = [
            {'opcode': 'MOV', 'args': [10, 'R0'], 'line_num': 1},
            {'opcode': 'MOV', 'args': [5, 'R1'], 'line_num': 2},
            {'opcode': 'ADD', 'args': ['R1', 'R0'], 'line_num': 3},
            {'opcode': 'HLT', 'args': [], 'line_num': 4}
        ]

        compiler = JITCompiler(insts)
        fn = compiler.compile()

        robot = Robot(0, 0, 'E')
        ctx = MockVMContext(insts)

        fn(robot, None, ctx)

        self.assertTrue(robot.halted)
        self.assertEqual(robot.registers['R0'], 15)

if __name__ == '__main__':
    unittest.main()
