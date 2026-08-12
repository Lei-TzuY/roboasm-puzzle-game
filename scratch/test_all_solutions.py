import os
import sys
import traceback

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from lexer import Lexer
from assembler import Assembler
from vm import VM
from level import Level

def test_level(lvl_id):
    lvl_file = f"levels/level{lvl_id}.json"
    asm_file = f"solutions/level{lvl_id}.asm"
    
    if not os.path.exists(lvl_file) or not os.path.exists(asm_file):
        return False, "Files not found"
        
    try:
        level = Level(lvl_file)
        grid = level.create_grid()
        
        with open(asm_file, 'r', encoding='utf-8') as f:
            code = f.read()
            
        lexer = Lexer(code)
        tokens = lexer.tokenize()
        
        assembler = Assembler(tokens, base_dir=os.path.dirname(os.path.abspath(asm_file)))
        instructions = assembler.assemble()
        
        vm = VM(instructions, grid, level.robots_config, data_memory=assembler.data_memory)
        
        steps = 0
        while not vm.halted and steps < 1000:
            vm.step()
            steps += 1
            won, msg = level.check_win(vm, vm.grid)
            if won:
                return True, f"Won in {steps} cycles. {msg}"
                
        won, msg = level.check_win(vm, vm.grid)
        if won:
            return True, f"Won in {steps} cycles. {msg}"
        else:
            return False, f"Failed after {steps} cycles: {msg}"
            
    except Exception as e:
        return False, f"Error: {e}\n{traceback.format_exc()}"

def main():
    print(f"{'Level':<10} | {'Status':<8} | {'Result / Cycles'}")
    print("-" * 60)
    
    all_ok = True
    for i in range(1, 36):
        ok, msg = test_level(i)
        status = "PASS" if ok else "FAIL"
        print(f"Level {i:<5} | {status:<8} | {msg}")
        if not ok:
            all_ok = False
            
    if all_ok:
        print("\nAll 35 level solutions verified successfully!")
        sys.exit(0)
    else:
        print("\nSome tests failed!")
        sys.exit(1)

if __name__ == '__main__':
    main()
