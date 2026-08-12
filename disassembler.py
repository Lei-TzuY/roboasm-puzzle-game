class Disassembler:
    def __init__(self, instructions, symbol_table=None):
        self.instructions = instructions
        self.symbol_table = symbol_table or {}

    def disassemble(self):
        # Pass 1: Find jump targets to generate labels
        jump_opcodes = {'JMP', 'JEQ', 'JNE', 'JLT', 'JGT', 'CALL'}
        jump_targets = set()

        for inst in self.instructions:
            opcode = inst.get('opcode', '').upper()
            args = inst.get('args', [])
            if opcode in jump_opcodes and len(args) > 0:
                if isinstance(args[0], int) and 0 <= args[0] < len(self.instructions):
                    jump_targets.add(args[0])

        # Reverse lookup for labels from symbol_table
        label_map = {}
        for sym, data in self.symbol_table.items():
            if data.get('type') == 'label':
                label_map[data.get('value')] = sym

        # Generate default label names for targets without existing label names
        for target_pc in sorted(jump_targets):
            if target_pc not in label_map:
                label_map[target_pc] = f"label_{target_pc}"

        # Pass 2: Format lines
        lines = []
        for pc, inst in enumerate(self.instructions):
            if pc in label_map:
                lines.append(f"\n{label_map[pc]}:")

            opcode = inst.get('opcode', '')
            args = inst.get('args', [])

            formatted_args = []
            if opcode in jump_opcodes and len(args) > 0 and isinstance(args[0], int) and args[0] in label_map:
                formatted_args.append(label_map[args[0]])
                formatted_args.extend([str(a) for a in args[1:]])
            else:
                formatted_args = [str(a) for a in args]

            arg_str = ", ".join(formatted_args) if formatted_args else ""
            inst_str = f"    {opcode:<6} {arg_str}".rstrip()
            lines.append(inst_str)

        return "\n".join(lines).strip()
