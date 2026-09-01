# RoboASM Authoritative Debugger

The server-served Web IDE uses persistent Python debugger sessions as the canonical execution timeline. A session keeps one VM, grid, shared RAM, robot state, IPC queue, cycle counter, and bounded reverse history alive across requests.

## Session API

```text
POST   /api/debug/sessions
GET    /api/debug/sessions/{session_id}
POST   /api/debug/sessions/{session_id}/step
POST   /api/debug/sessions/{session_id}/run
DELETE /api/debug/sessions/{session_id}
```

Signed stepping is unchanged:

```json
{"cycles": 1}
```

moves forward, while:

```json
{"cycles": -1}
```

restores the previous authoritative checkpoint.

## Breakpoints and advanced stop specs

`/run` remains backward compatible with the original line-breakpoint array:

```json
{
  "max_cycles": 16,
  "breakpoint_lines": [5, 12],
  "breakpoint_robot_id": 0
}
```

For advanced debugging, the same field can be a structured stop specification:

```json
{
  "max_cycles": 16,
  "breakpoint_robot_id": 0,
  "breakpoint_lines": {
    "lines": [5],
    "conditional_breakpoints": [
      {
        "line_num": 12,
        "condition": "R0 == 3 and RAM[0] != 7",
        "robot_id": 0
      }
    ],
    "watchpoints": [
      {"kind": "register", "robot_id": 0, "name": "R1"},
      {"kind": "ram", "address": 4}
    ]
  }
}
```

A plain line breakpoint and a conditional breakpoint are **pre-instruction stops**. The breakpointed instruction has not executed yet. The existing IDE rule is preserved: cycle-zero breakpoints do not immediately stop Run.

A register or RAM watchpoint is a **post-cycle mutation stop**. The cycle that changed the watched value has completed, and the response includes the old/new values. Because every executed cycle still creates a reverse checkpoint, one Step Back returns to the state immediately before the mutation.

## Web IDE advanced stops

On the canonical HTTP IDE, expand **Advanced Stops · conditional breakpoint / watchpoints** in the authoritative runtime panel. The controls are live; the next Run chunk reads them and forwards a structured stop specification to Python.

- **Conditional**: enable it, enter a source line, and enter a safe expression such as `R0 == 3 and RAM[0] != 7`. The currently selected robot is used unless an API client supplies another robot ID.
- **Register**: select `R0`–`R3`. Run pauses immediately after that register changes on the selected robot.
- **RAM**: enter an integer shared-memory address. Run pauses immediately after that address is created, removed, or changes value.
- Ordinary red-dot source breakpoints remain active at the same time and are included in the same server stop specification.

When a conditional breakpoint hits, the IDE reports the condition and source line. Watchpoint messages report the old and new values. All stop decisions are made by the authoritative Python session; the browser does not evaluate conditions locally. Disabling every advanced control preserves the legacy `breakpoint_lines: [...]` request shape exactly.

## Conditional breakpoint language

Conditions are parsed with Python's AST but are evaluated by a dedicated interpreter in `debug_expressions.py`; Python `eval()` is never used.

Available state names:

```text
R0 R1 R2 R3
INV X Y PC CYCLES
ZERO NEGATIVE
RAM[address]
```

Examples:

```text
R0 == 3
PC >= 5 and ZERO is False
RAM[0] != 7
INV is None
(R0 % 2) == 0 and CYCLES > 10
```

Allowed operations are intentionally limited to boolean logic, comparisons, unary operations, addition/subtraction/multiplication/floor-division/modulo, and basic bitwise AND/OR/XOR. Function calls, attribute access, containers, arbitrary subscripting, strings, shifts, and other Python syntax are rejected.

Expressions are limited to 256 characters, and integer literals/RAM indices must fit in signed 64-bit range. Runtime expression errors such as division by zero are returned as structured debugger errors without advancing the VM.

## Stop metadata

Conditional breakpoint example:

```json
{
  "stopped_by_breakpoint": true,
  "breakpoint": {
    "kind": "conditional",
    "robot_id": 0,
    "pc": 2,
    "line_num": 3,
    "condition": "R0 == 2",
    "cycle": 2
  }
}
```

RAM watchpoint example:

```json
{
  "stopped_by_watchpoint": true,
  "watchpoint": {
    "kind": "ram",
    "address": 0,
    "old_exists": false,
    "old_value": null,
    "new_exists": true,
    "new_value": 7,
    "cycle": 3
  }
}
```

Register watchpoint metadata additionally includes `robot_id` and register `name`.

## Validation

CI covers:

- safe expression parsing/evaluation and rejection of executable Python syntax;
- bounded literal arithmetic and rejection of shift-based resource abuse;
- conditional breakpoints stopping before the matching instruction;
- register and RAM watchpoints stopping after mutation;
- exact Step Back restoration to the pre-mutation checkpoint;
- real localhost HTTP structured stop specifications;
- Web advanced-stop editor serialization, conditional-hit decoration, watchpoint pause behavior, and legacy array fallback;
- compatibility with legacy `breakpoint_lines: [..]` requests;
- all existing level, runtime, optimizer, fuzz, Web-controller, and reverse-debugger gates.
