import os
import sys
import json
import argparse
import time
import glob
import re
from lexer import Lexer
from assembler import Assembler
from disassembler import Disassembler
from vm import VM
from level import Level

# Enable ANSI codes on Windows
if os.name == 'nt':
    os.system('')

try:
    import winsound
except ImportError:
    winsound = None

def play_sound(op):
    if not winsound: return
    if op in ['MOVE', 'TURN']:
        winsound.Beep(400, 50)
    elif op == 'PICK':
        winsound.Beep(600, 50)
    elif op == 'DROP':
        winsound.Beep(300, 50)
    elif op == 'CRASH':
        winsound.Beep(150, 300)
    elif op == 'VICTORY':
        winsound.Beep(440, 100)
        winsound.Beep(554, 100)
        winsound.Beep(659, 200)

# ANSI Colors
CYAN = '\033[96m'
YELLOW = '\033[93m'
GREEN = '\033[92m'
RED = '\033[91m'
GRAY = '\033[90m'
BLUE = '\033[94m'
RESET = '\033[0m'

def compile_bytecode(input_asm, output_bin, optimize=False):
    with open(input_asm, 'r', encoding='utf-8') as f:
        code = f.read()
    lexer = Lexer(code)
    tokens = lexer.tokenize()
    assembler = Assembler(tokens, base_dir=os.path.dirname(os.path.abspath(input_asm)))
    instructions = assembler.assemble(optimize=optimize)

    payload = {
        'instructions': instructions,
        'symbol_table': assembler.symbol_table,
        'data_memory': assembler.data_memory
    }
    with open(output_bin, 'w', encoding='utf-8') as f:
        json.dump(payload, f, indent=2)
    print(f"Successfully compiled '{input_asm}' -> '{output_bin}' ({len(instructions)} opcodes).")

def disassemble_bytecode(input_bin):
    with open(input_bin, 'r', encoding='utf-8') as f:
        payload = json.load(f)
    instructions = payload.get('instructions', [])
    symbol_table = payload.get('symbol_table', {})
    disasm = Disassembler(instructions, symbol_table)
    code = disasm.disassemble()
    print(f"=== Disassembly of '{input_bin}' ===")
    print(code)

def render_vm(vm, grid, level):
    os.system('cls' if os.name == 'nt' else 'clear')
    
    code_lines = []
    code_lines.append(f"=== RoboASM: {level.name} ===")
    code_lines.append(f"Goal: {level.description}")
    code_lines.append("Code:")
    
    start_idx = max(0, vm.robots[0].pc - 5) if vm.robots else 0
    end_idx = min(len(vm.instructions), start_idx + 10) if vm.robots else 0
    
    for i in range(start_idx, end_idx):
        inst = vm.instructions[i]
        prefix = "-> " if (vm.robots and i == vm.robots[0].pc) else "   "
        args_str = ", ".join(map(str, inst['args']))
        code_lines.append(f"{prefix}{i:02d}: {inst['opcode']} {args_str}")

    grid_lines = []
    grid_lines.append("Grid:")
    for y in range(grid.height):
        row = []
        for x in range(grid.width):
            robot_here = next((r for r in vm.robots if r.x == x and r.y == y), None)
            if robot_here:
                char = '^' if robot_here.facing == 'N' else 'v' if robot_here.facing == 'S' else '>' if robot_here.facing == 'E' else '<'
                row.append(f"{CYAN}{char}{RESET}")
            elif grid.is_wall(x, y):
                if (x, y) in grid.doors:
                    row.append(f"{RED}X{RESET}")
                else:
                    row.append(f"{GRAY}#{RESET}")
            elif grid.has_item(x, y):
                row.append(f"{YELLOW}i{RESET}")
            elif (x, y) in grid.buttons:
                row.append(f"{GREEN}O{RESET}")
            elif (x, y) in grid.conveyors:
                d = grid.conveyors[(x, y)]
                char = 'n' if d == 'N' else 's' if d == 'S' else 'e' if d == 'E' else 'w'
                row.append(f"{BLUE}{char}{RESET}")
            else:
                row.append('.')
        grid_lines.append(" ".join(row))
    
    grid_lines.append("")
    grid_lines.append("Robots State:")
    for idx, r in enumerate(vm.robots):
        inv_str = f"INV:{r.inventory}" if r.inventory is not None else "INV:[Empty]"
        grid_lines.append(f"[{idx}] PC:{r.pc:02d} | {inv_str} | Regs: {r.registers} | Flags: {r.flags}")
    
    max_lines = max(len(code_lines), len(grid_lines))
    while len(code_lines) < max_lines: code_lines.append("")
    while len(grid_lines) < max_lines: grid_lines.append("")
    
    for c, g in zip(code_lines, grid_lines):
        print(f"{c:<40} | {g}")
    print("-" * 70)

def run_vm(code, level_file):
    level = Level(level_file)
    grid = level.create_grid()

    lexer = Lexer(code)
    tokens = lexer.tokenize()
    
    assembler = Assembler(tokens, base_dir=os.path.dirname(os.path.abspath(level_file)))
    instructions = assembler.assemble()
    
    if not instructions:
        print("No instructions to execute!")
        input("Press Enter to return to editor...")
        return False, 0, 0

    vm = VM(instructions, grid, level.robots_config)
    
    steps = 0
    mode = 'auto'
    print("Compilation successful! Starting VM...")
    time.sleep(1)
    
    while not vm.halted and steps < 1000:
        if mode != 'fast':
            render_vm(vm, grid, level)
            
        if mode == 'step':
            try:
                cmd = input("Press Enter to step, 'f' to fast forward, 'a' to auto-play... ")
                if cmd == 'f': mode = 'fast'
                elif cmd == 'a': mode = 'auto'
            except KeyboardInterrupt:
                return False, 0, 0
        
        if mode == 'auto':
            ops_to_play = []
            for r in vm.robots:
                if not r.halted and r.pc < len(vm.instructions):
                    ops_to_play.append(vm.instructions[r.pc]['opcode'])
            prev_halted = [r.halted for r in vm.robots]
            
        vm.step()
        steps += 1
        
        if mode == 'auto':
            crashed = False
            for i, r in enumerate(vm.robots):
                if r.halted and not prev_halted[i] and r.pc < len(vm.instructions):
                    crashed = True
            
            if crashed:
                play_sound('CRASH')
            else:
                played_any = False
                for op in ops_to_play:
                    if op in ['MOVE', 'TURN']:
                        play_sound('MOVE')
                        played_any = True
                    elif op in ['PICK', 'DROP']:
                        play_sound(op)
                        played_any = True
                
                if not played_any:
                    time.sleep(0.15)
        
        if level.check_win(vm, grid)[0]:
            break
        
    render_vm(vm, grid, level)
    print("Program Halted.")
    
    won, msg = level.check_win(vm, grid)
    if won:
        play_sound('VICTORY')
        print(f"\n*** SUCCESS: {msg} ***")
        print(f"Score - Cycles: {steps} | Size: {len(instructions)}")
    else:
        print(f"\n--- FAILED: {msg} ---")
        
    input("\nPress Enter to return to editor...")
    return won, steps, len(instructions)

def editor(level_file):
    code_file = level_file.replace('levels', 'solutions').replace('.json', '.asm')
    os.makedirs('solutions', exist_ok=True)
    level = Level(level_file)
    
    if os.path.exists(code_file):
        with open(code_file, 'r', encoding='utf-8') as f:
            lines = f.read().split('\n')
            if len(lines) == 1 and not lines[0]:
                lines = []
    else:
        lines = []
        
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"=== Level: {level.name} ===")
        print(level.description)
        print("\n--- Code Editor ---")
        for i, line in enumerate(lines, 1):
            print(f"{i:02d}: {line}")
            
        print("\nCommands: [instruction] | 'insert <line> <inst>' | 'del <line>' | 'run' | 'save' | 'quit'")
        cmd = input("> ").strip()
        
        if not cmd:
            continue
            
        parts = cmd.split()
        op = parts[0].lower()
        
        if cmd in ['quit', 'exit', 'q']:
            return
        elif op == 'save':
            with open(code_file, 'w', encoding='utf-8') as f:
                f.write("\n".join(lines))
            print(f"Saved to {code_file}!")
            input("Press Enter...")
        elif op == 'run':
            won, cycles, size = run_vm("\n".join(lines), level_file)
            if won:
                profile_path = 'profile.json'
                profile = {}
                if os.path.exists(profile_path):
                    try:
                        with open(profile_path, 'r', encoding='utf-8') as f:
                            profile = json.load(f)
                    except: pass
                
                lvl_key = os.path.basename(level_file)
                new_record = False
                if lvl_key not in profile:
                    profile[lvl_key] = {'best_cycles': cycles, 'best_size': size}
                    new_record = True
                else:
                    if cycles < profile[lvl_key]['best_cycles']:
                        profile[lvl_key]['best_cycles'] = cycles
                        new_record = True
                    if size < profile[lvl_key]['best_size']:
                        profile[lvl_key]['best_size'] = size
                        new_record = True
                        
                if new_record:
                    print(f"\n{YELLOW}*** NEW RECORD SAVED! ***{RESET}")
                    input("Press Enter...")
                    with open(profile_path, 'w', encoding='utf-8') as f:
                        json.dump(profile, f, indent=2)
        elif op == 'del':
            try:
                l = int(parts[1]) - 1
                if 0 <= l < len(lines):
                    del lines[l]
            except:
                pass
        elif op == 'insert':
            try:
                l = int(parts[1]) - 1
                inst = " ".join(parts[2:])
                lines.insert(max(0, min(l, len(lines))), inst)
            except:
                pass
        else:
            lines.append(cmd)

def main_menu():
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"{CYAN}=================================={RESET}")
        print(f"{YELLOW}           ROBO ASM             {RESET}")
        print(f"{CYAN}=================================={RESET}\n")
        
        level_files = glob.glob("levels/*.json")
        def get_lvl_num(f):
            m = re.search(r'\d+', f)
            return int(m.group()) if m else 0
        level_files.sort(key=get_lvl_num)
        
        profile_path = 'profile.json'
        profile = {}
        if os.path.exists(profile_path):
            try:
                with open(profile_path, 'r', encoding='utf-8') as f:
                    profile = json.load(f)
            except: pass
        
        levels_data = []
        for lf in level_files:
            try:
                with open(lf, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    levels_data.append((lf, data.get('name', lf), os.path.basename(lf)))
            except:
                pass
                
        for i, (lf, name, lvl_key) in enumerate(levels_data):
            if lvl_key in profile:
                stats = profile[lvl_key]
                print(f"  {GREEN}{i+1}{RESET}. [X] {name} (Best: {stats['best_cycles']} cycles, {stats['best_size']} inst)")
            else:
                print(f"  {GREEN}{i+1}{RESET}. [ ] {name}")
            
        print(f"\n  {RED}q{RESET}. Quit")
        
        cmd = input("\nSelect an option: ").strip().lower()
        if cmd in ['q', 'quit', 'exit']:
            return None
            
        try:
            idx = int(cmd) - 1
            if 0 <= idx < len(levels_data):
                return levels_data[idx][0]
        except:
            pass

def main():
    parser = argparse.ArgumentParser(description="RoboASM Assembly Engine & Compiler")
    parser.add_argument("--level", help="Path to level JSON file", default=None)
    parser.add_argument("--web", action="store_true", help="Start the Web IDE server")
    parser.add_argument("--compile", help="Input assembly file to compile into bytecode", default=None)
    parser.add_argument("-o", "--output", help="Output bytecode file path", default="output.bin")
    parser.add_argument("--optimize", action="store_true", help="Enable bytecode AST optimization passes")
    parser.add_argument("--disassemble", help="Input bytecode file to disassemble", default=None)
    args = parser.parse_args()
    
    if args.compile:
        compile_bytecode(args.compile, args.output, optimize=args.optimize)
    elif args.disassemble:
        disassemble_bytecode(args.disassemble)
    elif args.web:
        from web_server import start_web_server
        start_web_server()
    elif args.level:
        editor(args.level)
    else:
        while True:
            lvl = main_menu()
            if lvl is None:
                print("Thanks for playing!")
                break
            editor(lvl)

if __name__ == "__main__":
    main()
