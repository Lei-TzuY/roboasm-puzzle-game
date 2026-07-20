class Robot:
    def __init__(self, x, y, facing):
        self.x = x
        self.y = y
        self.facing = facing
        self.inventory = None
        self.registers = {'R0': 0, 'R1': 0, 'R2': 0, 'R3': 0}
        self.flags = {'ZERO': False, 'NEGATIVE': False}
        self.pc = 0
        self.call_stack = []
        self.halted = False

    def get_val(self, arg):
        if isinstance(arg, int):
            return arg
        elif arg == 'INV':
            if self.inventory is None:
                raise ValueError("Cannot read empty INV")
            return self.inventory
        elif arg == 'X':
            return self.x
        elif arg == 'Y':
            return self.y
        elif arg in self.registers:
            return self.registers[arg]
        raise ValueError(f"Unknown argument {arg}")

    def set_val(self, arg, val):
        if arg == 'INV':
            self.inventory = val
        elif arg in self.registers:
            self.registers[arg] = val
        else:
            raise ValueError(f"Cannot set {arg}")

    def step(self, instructions, grid):
        if self.halted or self.pc >= len(instructions):
            self.halted = True
            return
            
        inst = instructions[self.pc]
        op = inst['opcode']
        args = inst['args']
        
        try:
            if op == 'MOV':
                val = self.get_val(args[0])
                self.set_val(args[1], val)
            
            elif op == 'ADD':
                v1 = self.get_val(args[0])
                v2 = self.get_val(args[1])
                self.set_val(args[1], v1 + v2)
                
            elif op == 'SUB':
                v1 = self.get_val(args[0])
                v2 = self.get_val(args[1])
                self.set_val(args[1], v2 - v1)
                
            elif op == 'MUL':
                v1 = self.get_val(args[0])
                v2 = self.get_val(args[1])
                self.set_val(args[1], v2 * v1)
                
            elif op == 'DIV':
                v1 = self.get_val(args[0])
                v2 = self.get_val(args[1])
                if v1 == 0:
                    raise ValueError("Division by zero")
                self.set_val(args[1], v2 // v1)
                
            elif op == 'MOD':
                v1 = self.get_val(args[0])
                v2 = self.get_val(args[1])
                if v1 == 0:
                    raise ValueError("Modulo by zero")
                self.set_val(args[1], v2 % v1)
                
            elif op == 'CMP':
                v1 = self.get_val(args[0])
                v2 = self.get_val(args[1])
                diff = v1 - v2
                self.flags['ZERO'] = (diff == 0)
                self.flags['NEGATIVE'] = (diff < 0)
                
            elif op == 'JMP':
                self.pc = args[0]
                return
                
            elif op == 'JEQ':
                if self.flags['ZERO']:
                    self.pc = args[0]
                    return
                    
            elif op == 'JNE':
                if not self.flags['ZERO']:
                    self.pc = args[0]
                    return
                    
            elif op == 'JLT':
                if self.flags['NEGATIVE']:
                    self.pc = args[0]
                    return

            elif op == 'JGT':
                if not self.flags['ZERO'] and not self.flags['NEGATIVE']:
                    self.pc = args[0]
                    return
                    
            elif op == 'CALL':
                self.call_stack.append(self.pc + 1)
                self.pc = args[0]
                return
                
            elif op == 'RET':
                if not self.call_stack:
                    raise ValueError("Empty call stack")
                self.pc = self.call_stack.pop()
                return
                    
            elif op == 'MOVE':
                nx, ny = self.x, self.y
                if self.facing == 'N': ny -= 1
                elif self.facing == 'S': ny += 1
                elif self.facing == 'E': nx += 1
                elif self.facing == 'W': nx -= 1
                
                if not grid.is_wall(nx, ny):
                    self.x, self.y = nx, ny
                    
            elif op == 'TURN':
                dirs = ['N', 'E', 'S', 'W']
                idx = dirs.index(self.facing)
                if args[0] == 'L':
                    self.facing = dirs[(idx - 1) % 4]
                elif args[0] == 'R':
                    self.facing = dirs[(idx + 1) % 4]
                    
            elif op == 'PICK':
                if self.inventory is None:
                    if (self.x, self.y) in grid.inboxes:
                        if not grid.inboxes[(self.x, self.y)]:
                            raise ValueError("Inbox is empty")
                        success, val = grid.remove_item(self.x, self.y)
                        if success:
                            self.inventory = val
                    elif grid.has_item(self.x, self.y):
                        success, val = grid.remove_item(self.x, self.y)
                        if success:
                            self.inventory = val
                    
            elif op == 'DROP':
                if self.inventory is not None:
                    success = grid.drop_item(self.x, self.y, self.inventory)
                    if success:
                        self.inventory = None

            elif op == 'HLT':
                self.halted = True
                return

            elif op == 'NOP':
                pass
            
            self.pc += 1
            
        except ValueError as e:
            # Exception halts this robot
            self.halted = True
            raise e

class VM:
    def __init__(self, instructions, grid, robots_config):
        self.instructions = instructions
        self.grid = grid
        self.robots = [Robot(cfg['x'], cfg['y'], cfg['facing']) for cfg in robots_config]
        self.halted = False

    def step(self):
        for robot in self.robots:
            if not robot.halted:
                try:
                    robot.step(self.instructions, self.grid)
                except ValueError as e:
                    robot.halted = True
                    
        all_finished = all(r.pc >= len(self.instructions) or r.halted for r in self.robots)
        if all_finished:
            self.halted = True
