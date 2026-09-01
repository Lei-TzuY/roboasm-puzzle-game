import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from level import Level
from level_schema import LevelValidationError
from runtime_api import execute_level_code

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


class DummyVM:
    robots = []


class TestLevelWinConditions(unittest.TestCase):
    def test_level1_is_not_won_at_initial_state(self):
        level = Level(os.path.join(ROOT_DIR, 'levels', 'level1.json'))
        grid = level.create_grid()

        won, message = level.check_win(DummyVM(), grid)

        self.assertFalse(won)
        self.assertIn('Item not at target position', message)

    def test_level1_bundled_solution_satisfies_item_at_condition(self):
        level_path = os.path.join(ROOT_DIR, 'levels', 'level1.json')
        solution_path = os.path.join(ROOT_DIR, 'solutions', 'level1.asm')
        with open(solution_path, 'r', encoding='utf-8') as f:
            code = f.read()

        result = execute_level_code(
            code,
            level_path,
            max_cycles=100,
            source_base_dir=ROOT_DIR,
        )

        self.assertTrue(result['won'])
        self.assertGreater(result['cycles'], 1)
        self.assertEqual(result['message'], 'All win conditions satisfied.')
        target_items = {
            (entry['x'], entry['y']): entry['value']
            for entry in result['state']['grid']['items']
        }
        self.assertIn((0, 0), target_items)

    def test_level_without_any_goal_is_rejected_at_load_time(self):
        definition = {
            'name': 'No Goal',
            'width': 2,
            'height': 2,
            'robot': {'x': 0, 'y': 0, 'facing': 'E'},
        }
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.json', encoding='utf-8', delete=False
        ) as f:
            json.dump(definition, f)
            path = f.name

        try:
            with self.assertRaises(LevelValidationError) as ctx:
                Level(path)
        finally:
            os.unlink(path)

        self.assertEqual(ctx.exception.path, '$')
        self.assertIn('must define win_conditions', ctx.exception.message)


if __name__ == '__main__':
    unittest.main()
