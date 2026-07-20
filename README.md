# RoboASM Puzzle Game

A programming puzzle game where players solve grid-based robot levels using a small assembly-like language.

The project includes:

- A lexer and assembler for the RoboASM language
- A virtual machine for executing robot programs
- Grid, wall, door, item, button, and conveyor mechanics
- 12 built-in levels
- Reference solutions for every level
- Terminal gameplay and a lightweight web UI

## Run

Terminal UI:

```powershell
python main.py
```

Web UI:

```powershell
python web_server.py
```

Then open the local URL printed by the server.

## Test

Validate all bundled solutions:

```powershell
python scratch\test_all_solutions.py
```

Current local audit: 12/12 bundled level solutions passing.

## Notes

The game is designed as a compact programming-languages and puzzle-systems prototype rather than a packaged commercial game.

