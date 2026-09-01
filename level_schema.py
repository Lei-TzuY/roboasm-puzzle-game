"""Validation helpers for RoboASM level JSON definitions.

The game intentionally keeps level files lightweight JSON rather than requiring a
third-party schema package.  This module provides the small amount of structural
and geometric validation the runtime needs before constructing a Grid.
"""

CARDINAL_DIRECTIONS = frozenset({'N', 'E', 'S', 'W'})
SUPPORTED_WIN_CONDITIONS = frozenset({'item_at', 'robot_at'})


class LevelValidationError(ValueError):
    """Raised when a level definition is malformed.

    ``path`` uses a compact JSON-style notation (for example
    ``robots[1].facing``), which makes errors useful in the CLI, CI, and HTTP API.
    """

    def __init__(self, path, message, source=None):
        self.path = path
        self.message = message
        self.source = source
        location = f"{source}: " if source else ''
        super().__init__(f"Level validation error: {location}{path}: {message}")


def _fail(path, message, source):
    raise LevelValidationError(path, message, source=source)


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _require_mapping(value, path, source):
    if not isinstance(value, dict):
        _fail(path, "must be an object", source)
    return value


def _require_list(value, path, source):
    if not isinstance(value, list):
        _fail(path, "must be an array", source)
    return value


def _require_int(value, path, source, minimum=None):
    if not _is_int(value):
        _fail(path, "must be an integer", source)
    if minimum is not None and value < minimum:
        _fail(path, f"must be >= {minimum}", source)
    return value


def _validate_coord(entry, path, width, height, source):
    _require_mapping(entry, path, source)
    x = _require_int(entry.get('x'), f"{path}.x", source)
    y = _require_int(entry.get('y'), f"{path}.y", source)
    if not 0 <= x < width:
        _fail(f"{path}.x", f"must be within 0..{width - 1}", source)
    if not 0 <= y < height:
        _fail(f"{path}.y", f"must be within 0..{height - 1}", source)
    return x, y


def _validate_coord_list(definition, key, width, height, source):
    entries = definition.get(key, [])
    _require_list(entries, key, source)
    seen = set()
    for index, entry in enumerate(entries):
        path = f"{key}[{index}]"
        coord = _validate_coord(entry, path, width, height, source)
        if coord in seen:
            _fail(path, f"duplicates coordinate {coord}", source)
        seen.add(coord)
    return entries


def _validate_robot(robot, path, width, height, source):
    _validate_coord(robot, path, width, height, source)
    facing = robot.get('facing')
    if not isinstance(facing, str) or facing.upper() not in CARDINAL_DIRECTIONS:
        _fail(
            f"{path}.facing",
            "must be one of N, E, S, W",
            source,
        )


def _validate_robots(definition, width, height, source):
    has_robot = 'robot' in definition
    has_robots = 'robots' in definition
    if has_robot and has_robots:
        _fail('$', "must not define both 'robot' and 'robots'", source)

    if has_robots:
        robots = _require_list(definition['robots'], 'robots', source)
        if not robots:
            _fail('robots', "must contain at least one robot", source)
        for index, robot in enumerate(robots):
            _validate_robot(robot, f"robots[{index}]", width, height, source)
        return len(robots)

    if has_robot:
        _validate_robot(definition['robot'], 'robot', width, height, source)
        return 1

    # Level has historically provided a default robot when omitted. Keep that
    # behavior valid rather than making old/custom levels suddenly illegal.
    return 1


def _validate_items(definition, width, height, source):
    return _validate_coord_list(definition, 'items', width, height, source)


def _validate_walls(definition, width, height, source):
    return _validate_coord_list(definition, 'walls', width, height, source)


def _validate_inboxes(definition, width, height, source):
    entries = _validate_coord_list(definition, 'inboxes', width, height, source)
    for index, entry in enumerate(entries):
        queue = entry.get('queue', [])
        _require_list(queue, f"inboxes[{index}].queue", source)
    return entries


def _validate_outboxes(definition, width, height, source):
    entries = _validate_coord_list(definition, 'outboxes', width, height, source)
    for index, entry in enumerate(entries):
        if 'expected' in entry:
            _require_list(entry['expected'], f"outboxes[{index}].expected", source)
    return entries


def _validate_conveyors(definition, width, height, source):
    entries = _validate_coord_list(definition, 'conveyors', width, height, source)
    for index, entry in enumerate(entries):
        direction = entry.get('dir')
        if not isinstance(direction, str) or direction.upper() not in CARDINAL_DIRECTIONS:
            _fail(
                f"conveyors[{index}].dir",
                "must be one of N, E, S, W",
                source,
            )
    return entries


def _validate_doors(definition, width, height, source):
    return _validate_coord_list(definition, 'doors', width, height, source)


def _validate_buttons(definition, width, height, source):
    entries = _validate_coord_list(definition, 'buttons', width, height, source)
    for index, entry in enumerate(entries):
        targets = entry.get('targets', [])
        _require_list(targets, f"buttons[{index}].targets", source)
        for target_index, target in enumerate(targets):
            _validate_coord(
                target,
                f"buttons[{index}].targets[{target_index}]",
                width,
                height,
                source,
            )
    return entries


def _validate_portals(definition, width, height, source):
    entries = _validate_coord_list(definition, 'portals', width, height, source)
    for index, entry in enumerate(entries):
        tx = _require_int(entry.get('target_x'), f"portals[{index}].target_x", source)
        ty = _require_int(entry.get('target_y'), f"portals[{index}].target_y", source)
        if not 0 <= tx < width:
            _fail(
                f"portals[{index}].target_x",
                f"must be within 0..{width - 1}",
                source,
            )
        if not 0 <= ty < height:
            _fail(
                f"portals[{index}].target_y",
                f"must be within 0..{height - 1}",
                source,
            )
    return entries


def _validate_win_conditions(definition, width, height, robot_count, source):
    conditions = definition.get('win_conditions', [])
    _require_list(conditions, 'win_conditions', source)
    for index, condition in enumerate(conditions):
        path = f"win_conditions[{index}]"
        _require_mapping(condition, path, source)
        condition_type = condition.get('type')
        if condition_type not in SUPPORTED_WIN_CONDITIONS:
            _fail(
                f"{path}.type",
                "must be one of item_at, robot_at",
                source,
            )
        _validate_coord(condition, path, width, height, source)
        if condition_type == 'robot_at' and 'robot_id' in condition:
            robot_id = _require_int(condition['robot_id'], f"{path}.robot_id", source, minimum=0)
            if robot_id >= robot_count:
                _fail(
                    f"{path}.robot_id",
                    f"must reference an existing robot (0..{robot_count - 1})",
                    source,
                )
    return conditions


def validate_level_definition(definition, source=None):
    """Validate and return *definition*.

    The function is deliberately dependency-free and does not mutate the input.
    It validates the fields consumed by ``Level``/``Grid`` while leaving unknown
    metadata keys available for future puzzle mechanics and editor annotations.
    """
    _require_mapping(definition, '$', source)

    if 'name' in definition and not isinstance(definition['name'], str):
        _fail('name', "must be a string", source)
    if 'description' in definition and not isinstance(definition['description'], str):
        _fail('description', "must be a string", source)

    width = _require_int(definition.get('width', 5), 'width', source, minimum=1)
    height = _require_int(definition.get('height', 5), 'height', source, minimum=1)
    robot_count = _validate_robots(definition, width, height, source)

    _validate_items(definition, width, height, source)
    _validate_walls(definition, width, height, source)
    _validate_inboxes(definition, width, height, source)
    outboxes = _validate_outboxes(definition, width, height, source)
    _validate_conveyors(definition, width, height, source)
    _validate_buttons(definition, width, height, source)
    _validate_doors(definition, width, height, source)
    _validate_portals(definition, width, height, source)
    win_conditions = _validate_win_conditions(
        definition,
        width,
        height,
        robot_count,
        source,
    )

    expected_output = definition.get('expected_output', [])
    _require_list(expected_output, 'expected_output', source)
    if expected_output and not outboxes:
        _fail('expected_output', "requires at least one outbox", source)

    has_outbox_goal = any('expected' in outbox for outbox in outboxes)
    if not win_conditions and not expected_output and not has_outbox_goal:
        _fail(
            '$',
            "must define win_conditions, expected_output, or an outbox expected sequence",
            source,
        )

    return definition
