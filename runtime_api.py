"""Headless execution helpers shared by HTTP clients and test tooling."""

import os

from assembler import Assembler
from level import Level
from lexer import Lexer
from vm import VM

MAX_RUN_CYCLES = 10_000
MAX_TRACE_CYCLES = 2_000


def validate_run_options(max_cycles=1000, capture_trace=False, optimize=False):
    if not isinstance(max_cycles, int) or isinstance(max_cycles, bool):
        raise ValueError("max_cycles must be an integer")
    if max_cycles < 0 or max_cycles > MAX_RUN_CYCLES:
        raise ValueError(f"max_cycles must be between 0 and {MAX_RUN_CYCLES}")
    if not isinstance(capture_trace, bool):
        raise ValueError("capture_trace must be a boolean")
    if not isinstance(optimize, bool):
        raise ValueError("optimize must be a boolean")
    if capture_trace and max_cycles > MAX_TRACE_CYCLES:
        raise ValueError(
            f"capture_trace requires max_cycles <= {MAX_TRACE_CYCLES}"
        )


def execute_level_code(
    code,
    level_path,
    max_cycles=1000,
    capture_trace=False,
    optimize=False,
    source_base_dir=None,
):
    """Assemble and execute *code* against a level, returning JSON-friendly data.

    ``source_base_dir`` controls how source-level ``#include`` directives are
    resolved. It defaults to the level file's directory for backwards
    compatibility; HTTP/editor callers should pass the directory that owns the
    source document (the repository root for the bundled Web IDE).
    """
    if not isinstance(code, str):
        raise ValueError("code must be a string")
    if not isinstance(level_path, (str, os.PathLike)):
        raise ValueError("level_path must be a filesystem path")
    if source_base_dir is not None and not isinstance(source_base_dir, (str, os.PathLike)):
        raise ValueError("source_base_dir must be a filesystem path")
    validate_run_options(
        max_cycles=max_cycles,
        capture_trace=capture_trace,
        optimize=optimize,
    )

    level_path = os.path.abspath(os.fspath(level_path))
    if source_base_dir is None:
        source_base_dir = os.path.dirname(level_path)
    else:
        source_base_dir = os.path.abspath(os.fspath(source_base_dir))

    level = Level(level_path)
    grid = level.create_grid()

    tokens = Lexer(code).tokenize()
    assembler = Assembler(tokens, base_dir=source_base_dir)
    instructions = assembler.assemble(optimize=optimize)
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
        'optimized': optimize,
        'instructions': instructions,
        'symbol_table': assembler.symbol_table,
        'data_memory': assembler.data_memory,
        'execution': execution,
        'state': vm.snapshot(),
    }
