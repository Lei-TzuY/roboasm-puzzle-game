import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ai_solver import AISolver

class TestAISolver(unittest.TestCase):

    def test_solve_level1(self):
        solver = AISolver("levels/level1.json")
        solution = solver.solve(max_depth=8)
        self.assertIsNotNone(solution)
        self.assertIn("MOVE", solution)

if __name__ == '__main__':
    unittest.main()
