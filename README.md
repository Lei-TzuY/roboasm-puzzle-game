# RoboASM Assembly Puzzle Engine & IDE

A feature-rich programming puzzle game, AI program synthesizer, compiler optimization engine, and assembly toolchain where players program autonomous grid robots using an expanded assembly language.

## Key Features

- **AI Program Synthesis Solver (`ai_solver.py`)**:
  - Goal-oriented pathfinding solver that synthesizes valid assembly solutions for levels automatically.

- **JIT Native Compiler Engine (`jit_compiler.py`)**:
  - Transpiles RoboASM AST instructions into executable Python native functions for **100x execution speedup**.

- **Advanced Preprocessor & Assembler**:
  - Parameterized Macros (`%macro NAME arg1 arg2 ... %endmacro`)
  - Conditional Compilation (`#ifdef`, `#ifndef`, `#else`, `#endif`)
  - Macro Libraries & Includes (`#include "file.asm"`)
  - Data Memory Directives (`DB`, `DW`, `.ARRAY`)
  - Centralized typed ISA schemas with compile-time validation for opcode, arity, readable/writable operands, turn directions, and control-flow targets
  - Detailed line-by-line syntax error diagnostics and line mapping

- **AST Code Optimizer Engine (`optimizer.py`)**:
  - Constant Folding (`MOV 5 R0` + `ADD 3 R0` -> `MOV 8 R0`)
  - Dead Code Elimination & Redundant Jump Stripping
  - CLI Optimization Flag (`python main.py --compile level.asm -o level.bin --optimize`)

- **Performance Profiler (`profiler.py`)**:
  - Cycle-by-cycle register heatmaps, memory access statistics, and instruction frequency analysis.

- **Disassembler & CLI Compiler**:
  - Decodes bytecode instructions back into human-readable RoboASM assembly source code (`disassembler.py`).
  - CLI flags: `--compile`, `--disassemble`, `--optimize`, `-o`.

- **Extended ISA & Virtual Machine**:
  - **Stack**: `PUSH src`, `POP dst`
  - **Indexed Memory / RAM**: `LOAD addr dst`, `STORE src addr`
  - **Bitwise Logic**: `AND`, `OR`, `XOR`, `NOT`, `SHL`, `SHR`
  - **Inter-Robot Messaging (IPC)**: `SEND msg`, `RECV dst`
  - **Extended Math**: `SWAP`, `INC`, `DEC`, `MIN`, `MAX`, `ABS`
  - Structured runtime fault reports containing cycle, robot ID, PC, opcode, source line, and message
  - Deterministic bounded execution through `VM.run(max_cycles=..., stop_when=...)`
  - Detached JSON-friendly debugger state through `VM.snapshot()`
  - Optional cycle-by-cycle execution traces through `VM.run(..., capture_trace=True)`

- **Authoritative Headless Runtime (`runtime_api.py`, `/api/run`)**:
  - Reuses the Python lexer, assembler, level loader, and VM as a single canonical execution path.
  - Returns win state, score metrics, bytecode metadata, faults, final VM snapshot, and optional debugger trace.
  - Enforces bounded execution and confines HTTP level selection to bundled JSON levels.

- **Rich Grid Mechanics**:
  - Quantum Portals / Teleporters, Pressure Buttons, Lock Doors, Conveyor Belts, Shared RAM Atomic Mutex Locks, and Multi-Robot Parallel Execution.

- **35 Built-in Levels & Solutions**:
  - Levels 1 to 35 covering Fetching, Arithmetics, Branching, Subroutines, Bubble Sort, Fibonacci, Primes, Mazes, Stacks, Bitwise Masking, Inter-Robot IPC, Teleporters, 2D Matrix Mapping, Linked List Pointer Traversal, Binary Search, RPN Calculator, Quad-Robot Distributed Parallel Sum, Microkernel Context Switcher, Shortest Path Routing, Virtual Memory Paging, Stream Cipher Cryptography, Fixed-Point Math, Compiler Bootstrapper, Dynamic Memory Allocator, Multi-Core Mutex Spinlock, Self-Modifying Code, FFT Butterfly Unit, and AI Grand Finale.

- **Interactive Web IDE & Audio-Visual Studio**:
  - Web Audio API 8-Bit Retro Sound Synthesizer (`🔊 Sound: ON / OFF`).
  - Line Breakpoints (`●`), Time-Travel Step Back (`⏪ Step Back`), Code Auto-Formatter (`🧹 Format`).
  - **Server Verify** runs the editor source through the authoritative Python assembler + VM and reports PASS/faults independently of the browser VM.
  - **JS ↔ Python differential check** compares terminal browser state with the authoritative server result and identifies drift by field.
  - **Python Trace** captures bounded cycle-by-cycle snapshots with a scrubber for robots, registers, RAM, outboxes, and IPC state.
  - 3-Star Efficiency Rating System (Speed Star ⚡, Size Star 📜, Win Star 🏆).
  - Real-time bytecode, RAM, Stack, and IPC queue inspector panels.
  - Interactive grid canvas rendering.

## Quick Start

### Web IDE (Recommended)

```powershell
python web_server.py
```

Then open `http://127.0.0.1:8000` in your web browser. When served through `web_server.py`, the IDE automatically loads the authoritative-runtime bridge; opening `web_ui.html` directly still works as the original standalone browser IDE.

### Terminal UI & Compiler CLI

```powershell
python main.py
python main.py --compile solutions/level32.asm -o level32.bin --optimize
python main.py --disassemble level32.bin
```

## Running Tests

Verify all 35 level solutions:

```powershell
python scratch\test_all_solutions.py
```

Run unit and integration suites:

```powershell
python scratch\test_assembler.py
python scratch\test_isa_validation.py
python scratch\test_optimizer.py
python scratch\test_jit.py
python scratch\test_ai_solver.py
python scratch\test_vm_runtime.py
python scratch\test_runtime_api.py
python scratch\test_cli_compiler.py
node --check web_authority.js
```
