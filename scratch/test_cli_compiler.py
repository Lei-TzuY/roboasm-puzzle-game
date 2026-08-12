import os
import sys
import json
import unittest
import subprocess

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

class TestCLICompiler(unittest.TestCase):

    def setUp(self):
        self.asm_file = "scratch_test.asm"
        self.bin_file = "scratch_test.bin"

    def tearDown(self):
        if os.path.exists(self.asm_file):
            os.remove(self.asm_file)
        if os.path.exists(self.bin_file):
            os.remove(self.bin_file)

    def test_cli_compile_and_disassemble(self):
        code = """
        #define NUM 10
        start:
            MOV NUM R0
            INC R0
            JMP start
        """
        with open(self.asm_file, 'w', encoding='utf-8') as f:
            f.write(code)

        # Run main.py --compile
        res = subprocess.run(
            [sys.executable, "main.py", "--compile", self.asm_file, "-o", self.bin_file],
            cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), '..')),
            capture_output=True,
            text=True
        )
        self.assertEqual(res.returncode, 0)
        self.assertTrue(os.path.exists(self.bin_file))

        with open(self.bin_file, 'r', encoding='utf-8') as f:
            payload = json.load(f)

        self.assertIn('instructions', payload)
        self.assertEqual(len(payload['instructions']), 3)

        # Run main.py --disassemble
        res2 = subprocess.run(
            [sys.executable, "main.py", "--disassemble", self.bin_file],
            cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), '..')),
            capture_output=True,
            text=True
        )
        self.assertEqual(res2.returncode, 0)
        self.assertIn("start:", res2.stdout)
        self.assertIn("MOV", res2.stdout)

if __name__ == '__main__':
    unittest.main()
