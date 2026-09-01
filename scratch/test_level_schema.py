import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from level import Level
from level_schema import LevelValidationError, validate_level_definition

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))


def valid_level():
    return {
        'name': 'Valid',
        'width': 3,
        'height': 2,
        'robot': {'x': 0, 'y': 0, 'facing': 'E'},
        'outboxes': [{'x': 2, 'y': 0}],
        'expected_output': [1],
    }


class TestLevelSchema(unittest.TestCase):
    def assert_invalid(self, definition, path_fragment):
        with self.assertRaises(LevelValidationError) as ctx:
            validate_level_definition(definition, source='fixture.json')
        self.assertIn(path_fragment, str(ctx.exception))
        self.assertEqual(ctx.exception.source, 'fixture.json')

    def test_all_bundled_level_definitions_validate(self):
        levels_dir = os.path.join(ROOT_DIR, 'levels')
        files = sorted(
            filename for filename in os.listdir(levels_dir)
            if filename.endswith('.json')
        )
        self.assertGreaterEqual(len(files), 35)
        for filename in files:
            path = os.path.join(levels_dir, filename)
            with open(path, 'r', encoding='utf-8') as f:
                definition = json.load(f)
            with self.subTest(level=filename):
                self.assertIs(
                    validate_level_definition(definition, source=filename),
                    definition,
                )

    def test_rejects_invalid_dimensions(self):
        definition = valid_level()
        definition['width'] = 0
        self.assert_invalid(definition, 'width')

        definition = valid_level()
        definition['height'] = True
        self.assert_invalid(definition, 'height')

    def test_rejects_robot_outside_grid_and_bad_facing(self):
        definition = valid_level()
        definition['robot']['x'] = 3
        self.assert_invalid(definition, 'robot.x')

        definition = valid_level()
        definition['robot']['facing'] = 'UP'
        self.assert_invalid(definition, 'robot.facing')

    def test_rejects_ambiguous_robot_configuration(self):
        definition = valid_level()
        definition['robots'] = [{'x': 1, 'y': 0, 'facing': 'W'}]
        self.assert_invalid(definition, "both 'robot' and 'robots'")

    def test_rejects_bad_conveyor_and_portal_geometry(self):
        definition = valid_level()
        definition['conveyors'] = [{'x': 1, 'y': 0, 'dir': 'NE'}]
        self.assert_invalid(definition, 'conveyors[0].dir')

        definition = valid_level()
        definition['portals'] = [
            {'x': 1, 'y': 0, 'target_x': 99, 'target_y': 1}
        ]
        self.assert_invalid(definition, 'portals[0].target_x')

    def test_rejects_invalid_robot_win_condition_reference(self):
        definition = valid_level()
        definition.pop('expected_output')
        definition.pop('outboxes')
        definition['win_conditions'] = [
            {'type': 'robot_at', 'robot_id': 3, 'x': 2, 'y': 1}
        ]
        self.assert_invalid(definition, 'win_conditions[0].robot_id')

    def test_rejects_expected_output_without_outbox(self):
        definition = valid_level()
        definition['outboxes'] = []
        self.assert_invalid(definition, 'expected_output')

    def test_rejects_level_without_any_goal(self):
        definition = valid_level()
        definition.pop('expected_output')
        definition['outboxes'] = [{'x': 2, 'y': 0}]
        self.assert_invalid(definition, 'must define win_conditions')

    def test_unknown_metadata_is_forward_compatible(self):
        definition = valid_level()
        definition['difficulty'] = 'expert'
        definition['editor_notes'] = {'theme': 'factory'}
        validate_level_definition(definition)

    def test_level_constructor_reports_validation_path_and_source(self):
        definition = valid_level()
        definition['robot']['y'] = 7
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

        self.assertEqual(ctx.exception.path, 'robot.y')
        self.assertEqual(ctx.exception.source, path)


if __name__ == '__main__':
    unittest.main()
