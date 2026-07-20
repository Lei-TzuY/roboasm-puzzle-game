import sys
import argparse
from lexer import Lexer
from assembler import Assembler
from vm import VM
from level import Level

def main():
    parser = argparse.ArgumentParser(description="RoboASM Test Runner")
    parser.add_argument("level_file", help="Path to the JSON level file")
    parser.add_argument("code_file", help="Path to the assembly code file")
    args = parser.parse_args()

    level = Level(args.level_file)
    grid = level.create_grid()

    with open(args.code_file, 'r') as f:
        code = f.read()

    lexer = Lexer(code)
    tokens = lexer.tokenize()
    
    assembler = Assembler(tokens)
    instructions = assembler.assemble()
    
    vm = VM(instructions, grid, level.robots_config)
    
    steps = 0
    while not vm.halted and steps < 1000:
        vm.step()
        grid.tick(vm.robots)
        steps += 1
        if level.check_win(vm, grid)[0]:
            break
        
    won, msg = level.check_win(vm, grid)
    print(f"Halted: {vm.halted}")
    print(f"Steps (Cycles): {steps}")
    print(f"Size: {len(instructions)}")
    print(f"Win condition met: {won}")
    print(f"Message: {msg}")

if __name__ == '__main__':
    main()
