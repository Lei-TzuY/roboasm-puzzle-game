import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from assembler import Assembler, AssemblerError
from lexer import Lexer


class TestISAValidation(unittest.TestCase):
    def assemble(self, code):
        return Assembler(Lexer(code).tokenize()).assemble()

    def test_unknown_opcode_is_rejected(self):
        with self.assertRaises(AssemblerError) as ctx:
            self.assemble('MVO 1 R0')

        self.assertIn("Unknown opcode 'MVO'", str(ctx.exception))
        self.assertEqual(ctx.exception.line_num, 1)

    def test_missing_argument_is_rejected(self):
        with self.assertRaises(AssemblerError) as ctx:
            self.assemble('MOV 1')

        self.assertIn("Opcode 'MOV' expects 2 arguments, got 1", str(ctx.exception))
        self.assertEqual(ctx.exception.line_num, 1)

    def test_extra_argument_is_rejected(self):
        with self.assertRaises(AssemblerError) as ctx:
            self.assemble('HLT now')

        self.assertIn("Opcode 'HLT' expects 0 arguments, got 1", str(ctx.exception))

    def test_zero_and_one_argument_opcodes_remain_valid(self):
        instructions = self.assemble('NOP\nTURN L\nHLT')
        self.assertEqual([inst['opcode'] for inst in instructions], ['NOP', 'TURN', 'HLT'])


if __name__ == '__main__':
    unittest.main()
