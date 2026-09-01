import json

from grid import Grid
from level_schema import validate_level_definition


class Level:
    def __init__(self, filename):
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)

        validate_level_definition(data, source=filename)

        self.name = data.get('name', 'Unnamed Level')
        self.description = data.get('description', '')
        self.width = data.get('width', 5)
        self.height = data.get('height', 5)

        if 'robots' in data:
            self.robots_config = data['robots']
        elif 'robot' in data:
            self.robots_config = [data['robot']]
        else:
            self.robots_config = [{"x": 0, "y": 0, "facing": "N"}]

        self.items = data.get('items', [])
        self.walls = data.get('walls', [])
        self.inboxes = data.get('inboxes', [])
        self.outboxes = data.get('outboxes', [])
        self.outbox_configs = self.outboxes
        self.conveyors = data.get('conveyors', [])
        self.buttons = data.get('buttons', [])
        self.doors = data.get('doors', [])
        self.portals = data.get('portals', [])
        self.expected_output = data.get('expected_output', [])
        self.win_conditions = data.get('win_conditions', [])

    def create_grid(self):
        grid = Grid(self.width, self.height)
        for item in self.items:
            grid.add_item(item['x'], item['y'], item.get('value', 0))
        for wall in self.walls:
            grid.walls.add((wall['x'], wall['y']))
        for inbox in self.inboxes:
            grid.inboxes[(inbox['x'], inbox['y'])] = list(inbox.get('queue', []))
        for outbox in self.outboxes:
            grid.outboxes[(outbox['x'], outbox['y'])] = []
        for conv in self.conveyors:
            grid.conveyors[(conv['x'], conv['y'])] = conv['dir']
        for btn in self.buttons:
            targets = [(t['x'], t['y']) for t in btn.get('targets', [])]
            grid.buttons[(btn['x'], btn['y'])] = targets
        for door in self.doors:
            grid.doors.add((door['x'], door['y']))
        for portal in self.portals:
            grid.portals[(portal['x'], portal['y'])] = (
                portal['target_x'],
                portal['target_y'],
            )
        return grid

    def _check_explicit_win_conditions(self, vm, grid):
        for condition in self.win_conditions:
            condition_type = condition.get('type')

            if condition_type == 'item_at':
                key = (condition.get('x'), condition.get('y'))
                if key not in grid.items:
                    return False, f"Item not at target position {key}."
                if 'value' in condition and grid.items[key] != condition['value']:
                    return False, (
                        f"Item at {key} has value {grid.items[key]}, "
                        f"expected {condition['value']}."
                    )
            elif condition_type == 'robot_at':
                x = condition.get('x')
                y = condition.get('y')
                robot_id = condition.get('robot_id')
                matches = [
                    robot for robot in vm.robots
                    if robot.x == x and robot.y == y
                    and (robot_id is None or robot.id == robot_id)
                ]
                if not matches:
                    return False, f"Robot not at target position ({x}, {y})."
            else:
                return False, f"Unsupported win condition type '{condition_type}'."

        return True, "All win conditions satisfied."

    def check_win(self, vm, grid):
        if self.win_conditions:
            return self._check_explicit_win_conditions(vm, grid)

        if self.expected_output:
            if not grid.outboxes:
                return False, "No outbox found."

            outbox_key = list(grid.outboxes.keys())[0]
            actual = grid.outboxes[outbox_key]

            if len(actual) < len(self.expected_output):
                return False, f"Waiting for output... {actual}"
            if len(actual) > len(self.expected_output):
                return False, (
                    f"Too much output. Expected {self.expected_output}, got {actual}"
                )

            if actual == self.expected_output:
                return True, "Output matches."
            return False, (
                f"Output mismatch. Expected {self.expected_output}, got {actual}"
            )

        configured_outboxes = [
            outbox for outbox in self.outbox_configs if 'expected' in outbox
        ]
        if not configured_outboxes:
            return False, "No win condition configured."

        for outbox in configured_outboxes:
            key = (outbox['x'], outbox['y'])
            actual = grid.outboxes.get(key, [])
            expected = outbox['expected']
            if len(actual) < len(expected):
                return False, f"Waiting for output at {key}..."
            if len(actual) > len(expected):
                return False, f"Too much output at {key}."
            if actual != expected:
                return False, f"Mismatch at {key}. Expected {expected}, got {actual}"

        return True, "All outputs match perfectly!"
