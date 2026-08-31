"""Headless execution helpers shared by HTTP clients and test tooling."""

import os

from assembler import Assembler
from level import Level
from lexer import Lexer
from vm import VM

MAX_RUN_CYCLES = 10_000
MAX_TRACE_CYCLES = 2_000


def validate_run_options(max_cycles=1000, capture_trace=False):
    if not isinstance(max_cycles, int) or isinstance(max_cycles, bool):
        raise ValueError("max_cycles must be an integer")
    if max_cycles < 0 or max_cycles > MAX_RUN_CYCLES:
        raise ValueError(f"max_cycles must be between 0 and {MAX_RUN_CYCLES}")
    if not isinstance(capture_trace, bool):
        raise ValueError("capture_trace must be a boolean")
    if capture_trace and max_cycles > MAX_TRACE_CYCLES:
        raise ValueError(
            f"capture_trace requires max_cycles <= {MAX_TRACE_CYCLES}"
        )


def execute_level_code(code, level_path, max_cycles=1000, capture_trace=False):
    """Assemble and execute *code* against a level, returning JSON-friendly data."""
    if not isinstance(code, str):
        raise ValueError("code must be a string")
    if not isinstance(level_path, (str, os.PathLike)):
        raise ValueError("level_path must be a filesystem path")
    validate_run_options(max_cycles=max_cycles, capture_trace=capture_trace)

    level_path = os.fspath(level_path)
    level = Level(level_path)
    grid = level.create_grid()

    tokens = Lexer(code).tokenize()
    assembler = Assembler(
        tokens,
        base_dir=os.path.dirname(os.path.abspath(level_path)),
    )
    instructions = assembler.assemble()
    vm = VM(
        instructions,
        grid,
        level.robots_config,
        data_memory=assembler.data_memory,
    )

    def stop_when(current_vm):
        return level.check_win(current_vm, current_vm.grid)[0]

    execution = vm.run(
        max_cycles=max_cycles,
        stop_when=stop_when,
        capture_trace=capture_trace,
    )
    won, message = level.check_win(vm, vm.grid)

    return {
        'status': 'success',
        'won': won,
        'message': message,
        'cycles': vm.cycles,
        'size': len(instructions),
        'instructions': instructions,
        'symbol_table': assembler.symbol_table,
        'data_memory': assembler.data_memory,
        'execution': execution,
        'state': vm.snapshot(),
    }
