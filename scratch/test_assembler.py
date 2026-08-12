import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from lexer import Lexer
from assembler import Assembler, AssemblerError
from disassembler import Disassembler

class TestAssemblerToolchain(unittest.TestCase):

    def test_basic_assembly(self):
        code = """
        // Simple test
        MOV 10 R0
        ADD R0 R1
        HLT
        """
        lexer = Lexer(code)
        tokens = lexer.tokenize()
        assembler = Assembler(tokens)
        insts = assembler.assemble()
        
        self.assertEqual(len(insts), 3)
        self.assertEqual(insts[0]['opcode'], 'MOV')
        self.assertEqual(insts[0]['args'], [10, 'R0'])

    def test_macros_with_args(self):
        code = """%macro SET_REG reg val
            MOV val reg
%endmacro

SET_REG R0 42
SET_REG R1 99"""
        lexer = Lexer(code)
        tokens = lexer.tokenize()
        assembler = Assembler(tokens)
        insts = assembler.assemble()
        
        self.assertEqual(len(insts), 2)
        self.assertEqual(insts[0]['opcode'], 'MOV')
        self.assertEqual(insts[0]['args'], [42, 'R0'])
        self.assertEqual(insts[1]['opcode'], 'MOV')
        self.assertEqual(insts[1]['args'], [99, 'R1'])

    def test_conditional_compilation(self):
        code = """#define FEATURE_A 1

#ifdef FEATURE_A
    MOV 1 R0
#else
    MOV 0 R0
#endif

#ifndef FEATURE_B
    MOV 100 R1
#endif"""
        lexer = Lexer(code)
        tokens = lexer.tokenize()
        assembler = Assembler(tokens)
        insts = assembler.assemble()
        
        self.assertEqual(len(insts), 2)
        self.assertEqual(insts[0]['args'], [1, 'R0'])
        self.assertEqual(insts[1]['args'], [100, 'R1'])

    def test_data_memory_directives(self):
        code = """
        DB 10 20 30
        DW 400 500
        """
        lexer = Lexer(code)
        tokens = lexer.tokenize()
        assembler = Assembler(tokens)
        insts = assembler.assemble()
        
        self.assertEqual(assembler.data_memory[0], 10)
        self.assertEqual(assembler.data_memory[1], 20)
        self.assertEqual(assembler.data_memory[2], 30)
        self.assertEqual(assembler.data_memory[3], 400)
        self.assertEqual(assembler.data_memory[4], 500)

    def test_disassembler(self):
        code = """
        start:
            MOV 5 R0
            JMP start
        """
        lexer = Lexer(code)
        tokens = lexer.tokenize()
        assembler = Assembler(tokens)
        insts = assembler.assemble()
        
        disasm = Disassembler(insts, assembler.symbol_table)
        disasm_code = disasm.disassemble()
        
        self.assertIn("start:", disasm_code)
        self.assertIn("MOV", disasm_code)
        self.assertIn("JMP", disasm_code)

if __name__ == '__main__':
    unittest.main()
