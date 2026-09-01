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
  - Constants through `#define` / `EQU`
  - Macro Libraries & Project Includes (`#include "file.asm"`)
  - Data Memory Directives (`DB`, `DW`, `.ARRAY`)
  - Centralized typed ISA schemas with compile-time validation for opcode, arity, readable/writable operands, turn directions, and control-flow targets
  - Detailed line-by-line syntax error diagnostics and line mapping
  - `web_preprocessor.js` mirrors the Python preprocessing order for the server-served Web IDE, including recursive project-local includes, constants, conditional compilation, macro expansion, labels, and initial data memory.

- **Control-Flow-Safe Optimizer (`optimizer.py`, `web_optimizer.js`)**:
  - Constant Folding (`MOV 5 R0` + `ADD 3 R0` -> `MOV 8 R0`)
  - Dead Code Elimination, NOP removal, and redundant jump stripping
  - Remaps numeric `JMP` / conditional-jump / `CALL` targets and label metadata after every index-changing rewrite
  - Blocks folding across secondary control-flow entry points
  - Iterates to a bounded fixed point, making one optimizer invocation idempotent even for chained rewrite opportunities
  - Python and Web optimizers are checked for optimized-bytecode and execution parity
  - CLI Optimization Flag (`python main.py --compile level.asm -o level.bin --optimize`)

- **Deterministic Optimizer Property Fuzzing (`scratch/test_optimizer_fuzz.py`)**:
  - Generates 128 reproducible, terminating forward-control-flow programs per CI run without external fuzzing dependencies.
  - Mixes arithmetic-fold chains, NOP compaction, conditional branches, unreachable blocks, and optional `CALL` / `RET` paths.
  - Verifies optimized vs. unoptimized terminal semantics, jump/call/label target validity, Web/Python optimized bytecode parity, and optimizer idempotence.
  - Every generated failure reports its deterministic seed and complete source for direct reproduction.

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
  - Mirrors the Web IDE optimizer option and exposes whether the returned bytecode is optimized.
  - Resolves editor `#include` directives from the Web IDE/project source root, matching `/api/assemble` behavior.
  - Enforces bounded execution and confines HTTP level selection to bundled JSON levels.

- **Persistent Authoritative Debug Sessions (`debug_sessions.py`, `/api/debug/sessions`)**:
  - Creates one canonical Python VM and advances that same VM across later HTTP requests instead of replaying source from cycle zero.
  - Supports session create/state/signed-step/run/delete operations with optional incremental trace capture.
  - Positive `step` cycles advance the timeline; negative cycles restore authoritative checkpoints for real reverse debugging.
  - Retains up to 256 full VM checkpoints per session, including robot state, stacks, shared RAM, IPC, grid items/inboxes/outboxes, open doors, halt/fault state, and cycle count.
  - Rewind preserves the shared-RAM object identity used by every robot and can recover from terminal wins or runtime faults without creating a new session.
  - Breakpoint-aware `run` accepts source-line breakpoints plus the selected robot, checks them before each next cycle, and stops with structured robot/PC/line/cycle metadata before executing the breakpointed instruction.
  - Every cycle executed inside a multi-cycle `run` chunk still records its own reverse checkpoint, so batching does not reduce Step Back fidelity.
  - Uses opaque session IDs, a 30-minute inactivity TTL, a 32-session cap, LRU eviction, and a thread-safe registry.
  - Reuses the same compiler/level/VM preparation path as `/api/run`, so optimizer and include semantics stay authoritative.
  - Session tests exercise real localhost HTTP forward/rewind persistence, breakpoint stops, terminal replay, fault recovery, bounded history, TTL refresh/expiration, LRU eviction, compile diagnostics, and request validation.

- **Authoritative Web Debugger Controller (`web_authority.js`)**:
  - On the canonical HTTP IDE path, the existing **Compile**, **Step**, **Run**, **Pause**, and **Step Back** controls are rebound to one persistent Python debugger timeline instead of executing the duplicated browser VM.
  - Python snapshots hydrate the existing grid, register/flag, stack, RAM, IPC, outbox, door, PC, cycle, and instruction inspectors after every authoritative forward or reverse operation.
  - **Run** uses adaptive server chunks instead of one HTTP request per cycle. With the current 1–10 speed slider it requests 1–16 cycles at a time and the server stops each chunk on a breakpoint, terminal state, or budget.
  - Source-line breakpoint semantics stay compatible with the previous IDE: cycle-zero breakpoints are ignored, the selected robot determines breakpoint hits, and a manual **Step** can cross a paused breakpoint.
  - Pressing **Pause** while a chunk request is in flight stops future chunks; the returned committed Python snapshot is still hydrated first so browser and server timelines cannot diverge.
  - **Step Back** sends a negative signed step to the same session, clears stale terminal stars, and becomes disabled automatically when no retained checkpoint remains.
  - Local `file://` use keeps the legacy JavaScript VM as a standalone fallback/differential engine with its original local history behavior.
  - `scratch/test_web_authority_controller.js` simulates the browser controller under Node and proves Compile → Step → chunked Run → Step Back → Run uses one session while Python RAM/robot/IPC/grid state is reflected into the legacy visual model.

- **Cross-Runtime Verification (`scratch/test_cross_runtime.py`)**:
  - Extracts the actual embedded JavaScript `lex` / `Grid` / `Robot` / `VM` implementation from `web_ui.html`, installs the same Web compiler/runtime layers used by the server, and executes it headlessly under Node.
  - Compares JavaScript and authoritative Python snapshots **cycle by cycle**, including robot state, flags, stacks, RAM, IPC, items, inboxes, outboxes, doors, cycles, and halt state.
  - Covers 19 bundled levels, including RAM/data-heavy Levels 18, 21, 22, 25, 26, 27, 31, and 33.
  - Adds six explicit semantic/compiler regression cases covering `NOOP`, negative modulo, wide bitwise integers, shift faults, `#define` + `EQU` + conditional macros, and `#include "stdlib.asm"`.
  - Runs as a dedicated CI gate so semantic drift is detected at the first differing cycle.

- **Validated Level Assets (`level_schema.py`)**:
  - Validates all 35 level JSON definitions before execution, including dimensions, coordinates, robot facing, portals, buttons/doors, conveyors, outputs, and win conditions.
  - Produces precise JSON-style error paths such as `portals[0].target_x`.

- **Rich Grid Mechanics**:
  - Quantum Portals / Teleporters, Pressure Buttons, Lock Doors, Conveyor Belts, Shared RAM Atomic Mutex Locks, and Multi-Robot Parallel Execution.

- **35 Built-in Levels & Solutions**:
  - Levels 1 to 35 covering Fetching, Arithmetics, Branching, Subroutines, Bubble Sort, Fibonacci, Primes, Mazes, Stacks, Bitwise Masking, Inter-Robot IPC, Teleporters, 2D Matrix Mapping, Linked List Pointer Traversal, Binary Search, RPN Calculator, Quad-Robot Distributed Parallel Sum, Microkernel Context Switcher, Shortest Path Routing, Virtual Memory Paging, Stream Cipher Cryptography, Fixed-Point Math, Compiler Bootstrapper, Dynamic Memory Allocator, Multi-Core Mutex Spinlock, Self-Modifying Code, FFT Butterfly Unit, and AI Grand Finale.

- **Interactive Web IDE & Audio-Visual Studio**:
  - Web Audio API 8-Bit Retro Sound Synthesizer (`🔊 Sound: ON / OFF`).
  - Line Breakpoints (`●`), authoritative Time-Travel Step Back (`⏪ Step Back`), Code Auto-Formatter (`🧹 Format`).
  - **Server Verify** runs the editor source through the authoritative Python assembler + VM and reports PASS/faults independently of the persistent debugger session.
  - Server Verify mirrors the IDE **Optimize** checkbox so bytecode size/cycle comparisons are made in the same compile mode.
  - **JS ↔ Python differential check** compares terminal browser state with the authoritative server result and identifies drift by field.
  - **Python Trace** captures bounded cycle-by-cycle snapshots with a scrubber for robots, registers, RAM, outboxes, and IPC state.
  - The canonical server-served IDE bootstraps in deterministic order: project-local `.asm` include map → `web_optimizer.js` → `web_preprocessor.js` → `web_runtime_compat.js` → `web_authority.js` → `initUI()`.
  - `initUI()` is deferred on the HTTP path so the first automatic compile cannot race ahead of compiler/runtime compatibility installation.
  - Initial RAM produced by data directives is available to every Web robot from cycle 0 through the same shared-memory object used by `LOAD`/`STORE`.
  - 3-Star Efficiency Rating System (Speed Star ⚡, Size Star 📜, Win Star 🏆).
  - Real-time bytecode, RAM, Stack, and IPC queue inspector panels.
  - Interactive grid canvas rendering.

## Quick Start

### Web IDE (Recommended)

```powershell
python web_server.py
```

Then open `http://127.0.0.1:8000` in your web browser. On this canonical HTTP path, Compile/Step/Run/Pause/Step Back operate on a persistent authoritative Python VM and the returned snapshots drive the existing visual debugger. Opening `web_ui.html` directly still works as the legacy standalone JavaScript IDE and remains useful as a fallback/differential runtime.

### Debug Session API

Create a persistent debugger session with `POST /api/debug/sessions`, then use:

```text
GET    /api/debug/sessions/{session_id}
POST   /api/debug/sessions/{session_id}/step   {"cycles": 1}   # forward
POST   /api/debug/sessions/{session_id}/step   {"cycles": -1}  # rewind
POST   /api/debug/sessions/{session_id}/run    {"max_cycles": 16, "breakpoint_lines": [5, 12], "breakpoint_robot_id": 0, "capture_trace": false}
DELETE /api/debug/sessions/{session_id}
```

`run` executes at most `max_cycles` on the existing VM and can stop earlier before a selected robot reaches one of the requested source lines. Its `execution` object reports `stopped_by_breakpoint` plus `{robot_id, pc, line_num, cycle}` metadata when applicable. A session keeps the same Python VM, grid, RAM, robot stacks/registers, IPC queue, cycle counter, and a bounded 256-checkpoint reverse history alive between requests.

### Terminal UI & Compiler CLI

```powershell
python main.py
python main.py --compile solutions/level32.asm -o level32.bin --optimize
python main.py --disassemble level32.bin
```

## Running Tests

Verify all 35 level definitions and solutions:

```powershell
python scratch\validate_levels.py
python scratch\test_all_solutions.py
```

Run cross-runtime, Web-controller, and optimizer verification:

```powershell
node scratch\test_web_authority_controller.js
python scratch\test_cross_runtime.py
python scratch\test_optimizer_control_flow.py
python scratch\test_optimizer_parity.py
python scratch\test_optimizer_fuzz.py
```

Run unit and integration suites:

```powershell
python scratch\test_assembler.py
python scratch\test_isa_validation.py
python scratch\test_optimizer.py
python scratch\test_jit.py
python scratch\test_ai_solver.py
python scratch\test_level.py
python scratch\test_level_schema.py
python scratch\test_vm_runtime.py
python scratch\test_runtime_api.py
python scratch\test_debug_sessions.py
python scratch\test_debug_breakpoints.py
python scratch\test_cli_compiler.py
node --check web_optimizer.js
node --check web_preprocessor.js
node --check web_runtime_compat.js
node --check web_authority.js
node --check scratch\js_runtime_runner.js
node --check scratch\test_web_authority_controller.js
```
