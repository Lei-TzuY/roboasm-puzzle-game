import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import traceback
from lexer import Lexer
from assembler import Assembler
from vm import VM
from level import Level

def main():
    level = Level("levels/level12.json")
    grid = level.create_grid()

    with open("solutions/level12.asm", 'r') as f:
        code = f.read()

    lexer = Lexer(code)
    tokens = lexer.tokenize()
    
    assembler = Assembler(tokens)
    instructions = assembler.assemble()
    
    vm = VM(instructions, grid, level.robots_config)
    
    print("Initial Robot State:", [(r.x, r.y, r.facing) for r in vm.robots])
    
    steps = 0
    while not vm.halted and steps < 100:
        robot = vm.robots[0]
        pc = robot.pc
        inst = instructions[pc] if pc < len(instructions) else None
        print(f"Step {steps+1:02d} | PC: {pc:02d} | Inst: {inst} | Pos: ({robot.x}, {robot.y}) | Facing: {robot.facing} | Inv: {robot.inventory}")
        try:
            robot.step(vm.instructions, vm.grid)
        except Exception as e:
            print("EXCEPTION RAISED:")
            traceback.print_exc()
            break
        grid.tick(vm.robots)
        steps += 1
        won, msg = level.check_win(vm, grid)
        if won:
            print(f"WON AT STEP {steps}! Message: {msg}")
            break
            
    print(f"End state. Halted: {vm.halted}. Outboxes content: {grid.outboxes}")

if __name__ == '__main__':
    main()
