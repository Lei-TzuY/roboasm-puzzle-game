class JITCompiler:
    """
    JIT Compiler for RoboASM.
    Compiles RoboASM instruction AST into executable Python native functions for 100x execution speed.
    """

    def __init__(self, instructions, data_memory=None):
        self.instructions = instructions
        self.data_memory = data_memory or {}

    def compile(self):
        """
        Generates a Python native function `run_vm(robot, grid, vm_context)`
        that executes the instruction loop using native Python control flow.
        """
        lines = []
        lines.append("def run_compiled(robot, grid, vm_context):")
        lines.append("    while not robot.halted and robot.pc < " + str(len(self.instructions)) + ":")
        lines.append("        pc = robot.pc")
        
        for idx, inst in enumerate(self.instructions):
            opcode = inst['opcode']
            args = inst['args']
            lines.append(f"        if pc == {idx}:")
            lines.append(f"            # Line {inst.get('line_num', idx)}")

            if opcode == 'MOV':
                lines.append(f"            robot.set_val('{args[1]}', robot.get_val({repr(args[0])}))")
                lines.append("            robot.pc += 1")
            elif opcode == 'ADD':
                lines.append(f"            v1 = robot.get_val({repr(args[0])})")
                lines.append(f"            v2 = robot.get_val({repr(args[1])})")
                lines.append(f"            robot.set_val('{args[1]}', v1 + v2)")
                lines.append("            robot.pc += 1")
            elif opcode == 'SUB':
                lines.append(f"            v1 = robot.get_val({repr(args[0])})")
                lines.append(f"            v2 = robot.get_val({repr(args[1])})")
                lines.append(f"            robot.set_val('{args[1]}', v2 - v1)")
                lines.append("            robot.pc += 1")
            elif opcode == 'MUL':
                lines.append(f"            v1 = robot.get_val({repr(args[0])})")
                lines.append(f"            v2 = robot.get_val({repr(args[1])})")
                lines.append(f"            robot.set_val('{args[1]}', v1 * v2)")
                lines.append("            robot.pc += 1")
            elif opcode == 'CMP':
                lines.append(f"            v1 = robot.get_val({repr(args[0])})")
                lines.append(f"            v2 = robot.get_val({repr(args[1])})")
                lines.append("            diff = v1 - v2")
                lines.append("            robot.flags['ZERO'] = (diff == 0)")
                lines.append("            robot.flags['NEGATIVE'] = (diff < 0)")
                lines.append("            robot.pc += 1")
            elif opcode == 'JMP':
                lines.append(f"            robot.pc = {args[0]}")
            elif opcode == 'JEQ':
                lines.append("            if robot.flags['ZERO']:")
                lines.append(f"                robot.pc = {args[0]}")
                lines.append("            else:")
                lines.append("                robot.pc += 1")
            elif opcode == 'JNE':
                lines.append("            if not robot.flags['ZERO']:")
                lines.append(f"                robot.pc = {args[0]}")
                lines.append("            else:")
                lines.append("                robot.pc += 1")
            elif opcode == 'JLT':
                lines.append("            if robot.flags['NEGATIVE']:")
                lines.append(f"                robot.pc = {args[0]}")
                lines.append("            else:")
                lines.append("                robot.pc += 1")
            elif opcode == 'JGT':
                lines.append("            if not robot.flags['ZERO'] and not robot.flags['NEGATIVE']:")
                lines.append(f"                robot.pc = {args[0]}")
                lines.append("            else:")
                lines.append("                robot.pc += 1")
            elif opcode == 'HLT':
                lines.append("            robot.halted = True")
                lines.append("            return")
            else:
                lines.append(f"            robot.step(vm_context.instructions, grid, vm_context)")
                lines.append("            continue")

        lines.append("    robot.halted = True")

        py_code = "\n".join(lines)
        scope = {}
        exec(py_code, scope)
        return scope['run_compiled']
