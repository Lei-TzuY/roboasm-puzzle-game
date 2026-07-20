class Assembler:
    def __init__(self, tokens):
        self.tokens = tokens
        self.labels = {}
        self.instructions = []

    def assemble(self):
        # Pass 0: Find macros and substitute them
        macros = {}
        filtered_tokens = []
        for token_line in self.tokens:
            parts = token_line['parts']
            if parts[0].lower() in ('#define', '@define'):
                if len(parts) >= 3:
                    macros[parts[1]] = parts[2]
                continue
            filtered_tokens.append(token_line)
            
        # Substitute macros in arguments
        for token_line in filtered_tokens:
            parts = token_line['parts']
            new_parts = []
            for part in parts:
                if part in macros:
                    new_parts.append(macros[part])
                else:
                    new_parts.append(part)
            token_line['parts'] = new_parts
            
        self.tokens = filtered_tokens

        # Pass 1: Find labels
        inst_idx = 0
        for token_line in self.tokens:
            parts = token_line['parts']
            if parts[0].endswith(':'):
                label_name = parts[0][:-1]
                self.labels[label_name] = inst_idx
                if len(parts) > 1:
                    inst_idx += 1
            else:
                inst_idx += 1

        # Pass 2: Generate bytecode
        for token_line in self.tokens:
            parts = token_line['parts']
            if parts[0].endswith(':'):
                if len(parts) == 1:
                    continue
                parts = parts[1:]
            
            opcode = parts[0].upper()
            args = parts[1:]
            
            # Resolve labels in arguments
            resolved_args = []
            for arg in args:
                if arg in self.labels:
                    resolved_args.append(self.labels[arg])
                else:
                    try:
                        resolved_args.append(int(arg))
                    except ValueError:
                        resolved_args.append(arg)
            
            self.instructions.append({
                'opcode': opcode,
                'args': resolved_args,
                'line_num': token_line['line_num']
            })
            
        return self.instructions
