import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from assembler import Assembler, AssemblerError
from lexer import Lexer


class TestISAValidation(unittest.TestCase):
    def assemble(self, code):
        return Assembler(Lexer(code).tokenize()).assemble()

    def assert_assembly_error(self, code, message):
        with self.assertRaises(AssemblerError) as ctx:
            self.assemble(code)
        self.assertIn(message, str(ctx.exception))
        return ctx.exception

    def test_unknown_opcode_is_rejected(self):
        exc = self.assert_assembly_error('MVO 1 R0', "Unknown opcode 'MVO'")
        self.assertEqual(exc.line_num, 1)

    def test_missing_argument_is_rejected(self):
        exc = self.assert_assembly_error(
            'MOV 1',
            "Opcode 'MOV' expects 2 arguments, got 1",
        )
        self.assertEqual(exc.line_num, 1)

    def test_extra_argument_is_rejected(self):
        self.assert_assembly_error(
            'HLT now',
            "Opcode 'HLT' expects 0 arguments, got 1",
        )

    def test_read_only_destination_is_rejected(self):
        self.assert_assembly_error(
            'MOV 1 X',
            "must be writable (R0-R3 or INV)",
        )
        self.assert_assembly_error(
            'INC 9',
            "must be writable (R0-R3 or INV)",
        )

    def test_invalid_turn_direction_is_rejected(self):
        self.assert_assembly_error(
            'TURN N',
            "must be L, LEFT, R, or RIGHT",
        )

    def test_jump_target_must_resolve_to_instruction_address(self):
        self.assert_assembly_error(
            'JMP R0',
            "must resolve to an instruction address",
        )

    def test_jump_target_is_range_checked(self):
        self.assert_assembly_error(
            'JMP 99\nHLT',
            "target 99 is outside program range 0..2",
        )
        self.assert_assembly_error(
            'JMP -1',
            "target cannot be negative",
        )

    def test_trailing_label_is_valid_exit_target(self):
        instructions = self.assemble('JMP done\nMOV 1 R0\ndone:')
        self.assertEqual(instructions[0]['args'], [2])

    def test_valid_readable_and_writable_operands(self):
        instructions = self.assemble(
            'MOV Y R0\nLOAD R0 INV\nSTORE X R1\nSHL R1 2\nHLT'
        )
        self.assertEqual(len(instructions), 5)

    def test_constants_are_validated_after_resolution(self):
        instructions = self.assemble('#define DIR LEFT\nTURN DIR\nHLT')
        self.assertEqual(instructions[0]['args'], ['LEFT'])

        self.assert_assembly_error(
            '#define DEST X\nMOV 1 DEST',
            "must be writable (R0-R3 or INV)",
        )

    def test_zero_and_one_argument_opcodes_remain_valid(self):
        instructions = self.assemble('NOP\nNOOP\nTURN L\nHLT')
        self.assertEqual(
            [inst['opcode'] for inst in instructions],
            ['NOP', 'NOOP', 'TURN', 'HLT'],
        )


if __name__ == '__main__':
    unittest.main()
