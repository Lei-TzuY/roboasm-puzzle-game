import os
import re

from isa import format_arity_error, get_opcode_arity, validate_instruction_operands


class AssemblerError(Exception):
    def __init__(self, message, line_num=None):
        line_str = f"Line {line_num}: " if line_num is not None else ""
        super().__init__(f"Assembler Error: {line_str}{message}")
        self.line_num = line_num
        self.message = message


class Assembler:
    def __init__(self, tokens, base_dir=None, stdlib=None):
        self.raw_tokens = tokens
        self.base_dir = base_dir or "."
        self.stdlib = stdlib or {}
        self.labels = {}
        self.constants = {}
        self.data_memory = {}
        self.instructions = []
        self.symbol_table = {}

    def _validate_instructions(self):
        instruction_count = len(self.instructions)
        for instruction in self.instructions:
            error = validate_instruction_operands(
                instruction['opcode'],
                instruction['args'],
                instruction_count=instruction_count,
            )
            if error:
                raise AssemblerError(error, instruction.get('line_num'))

    def assemble(self, optimize=False):
        tokens = self._process_includes(self.raw_tokens)
        tokens = self._process_constants_and_data(tokens)
        tokens = self._process_conditionals(tokens)
        tokens = self._process_macros(tokens)

        inst_idx = 0
        filtered_tokens = []
        for token_line in tokens:
            parts = token_line['parts']
            if not parts:
                continue

            first = parts[0]
            if first.endswith(':'):
                label_name = first[:-1]
                if not label_name.isidentifier() and not label_name.replace('.', '_').isidentifier():
                    raise AssemblerError(f"Invalid label name '{label_name}'", token_line.get('line_num'))

                self.labels[label_name] = inst_idx
                self.symbol_table[label_name] = {'type': 'label', 'value': inst_idx}

                if len(parts) > 1:
                    token_line['parts'] = parts[1:]
                    filtered_tokens.append(token_line)
                    inst_idx += 1
            else:
                filtered_tokens.append(token_line)
                inst_idx += 1

        self.instructions = []
        for token_line in filtered_tokens:
            parts = token_line['parts']
            line_num = token_line.get('line_num')

            opcode = parts[0].upper()
            raw_args = parts[1:]

            expected_arity = get_opcode_arity(opcode)
            if expected_arity is None:
                raise AssemblerError(f"Unknown opcode '{opcode}'", line_num)
            if len(raw_args) != expected_arity:
                raise AssemblerError(
                    format_arity_error(opcode, expected_arity, len(raw_args)),
                    line_num,
                )

            resolved_args = []
            for arg in raw_args:
                if arg in self.constants:
                    resolved_args.append(self.constants[arg])
                elif arg in self.labels:
                    resolved_args.append(self.labels[arg])
                else:
                    try:
                        resolved_args.append(int(arg))
                    except ValueError:
                        resolved_args.append(arg.upper())

            self.instructions.append({
                'opcode': opcode,
                'args': resolved_args,
                'line_num': line_num,
            })

        self._validate_instructions()

        if optimize:
            from optimizer import Optimizer
            optimizer = Optimizer(self.instructions, self.labels)
            self.instructions = optimizer.optimize()
            self.labels = dict(optimizer.labels)
            for name, value in self.labels.items():
                entry = self.symbol_table.get(name)
                if entry and entry.get('type') == 'label':
                    entry['value'] = value
            # Optimization changes instruction indexes. Revalidate the final
            # bytecode so stale/out-of-range control-flow targets can never
            # escape into the VM or serialized compiler output.
            self._validate_instructions()

        return self.instructions

    def _process_includes(self, tokens, depth=0):
        if depth > 10:
            raise AssemblerError("Max include recursion depth exceeded")

        expanded = []
        for t in tokens:
            parts = t['parts']
            first = parts[0].lower()
            if first in ('#include', '@include', 'include'):
                if len(parts) < 2:
                    raise AssemblerError("Missing include target file", t.get('line_num'))
                target = parts[1].strip('"\'')

                inc_code = None
                if target in self.stdlib:
                    inc_code = self.stdlib[target]
                else:
                    inc_path = os.path.join(self.base_dir, target)
                    if os.path.exists(inc_path):
                        with open(inc_path, 'r', encoding='utf-8') as f:
                            inc_code = f.read()

                if inc_code is None:
                    raise AssemblerError(f"Include file '{target}' not found", t.get('line_num'))

                from lexer import Lexer
                sub_lexer = Lexer(inc_code)
                sub_tokens = sub_lexer.tokenize()
                expanded.extend(self._process_includes(sub_tokens, depth + 1))
            else:
                expanded.append(t)
        return expanded

    def _process_conditionals(self, tokens):
        result = []
        stack = [True]

        for t in tokens:
            parts = t['parts']
            first = parts[0].lower()

            if first in ('#ifdef', '@ifdef'):
                symbol = parts[1] if len(parts) > 1 else ''
                active = stack[-1] and (symbol in self.constants or symbol in self.labels)
                stack.append(active)
                continue
            elif first in ('#ifndef', '@ifndef'):
                symbol = parts[1] if len(parts) > 1 else ''
                active = stack[-1] and (symbol not in self.constants and symbol not in self.labels)
                stack.append(active)
                continue
            elif first in ('#else', '@else'):
                if len(stack) <= 1:
                    raise AssemblerError("Unexpected #else directive", t.get('line_num'))
                stack[-1] = stack[-2] and not stack[-1]
                continue
            elif first in ('#endif', '@endif'):
                if len(stack) <= 1:
                    raise AssemblerError("Unexpected #endif directive", t.get('line_num'))
                stack.pop()
                continue

            if stack[-1]:
                result.append(t)

        if len(stack) > 1:
            raise AssemblerError("Unterminated #ifdef/#ifndef directive block")

        return result

    def _process_macros(self, tokens):
        macro_defs = {}
        filtered = []
        in_macro = None

        for t in tokens:
            parts = t['parts']
            first = parts[0].lower()

            if first in ('%macro', '#macro', 'macro'):
                if len(parts) < 2:
                    raise AssemblerError("Macro definition requires a name", t.get('line_num'))
                macro_name = parts[1]
                macro_args = parts[2:]
                in_macro = {
                    'name': macro_name,
                    'args': macro_args,
                    'body': [],
                }
                continue

            if first in ('%endmacro', '#endmacro', 'endmacro'):
                if not in_macro:
                    raise AssemblerError("Unexpected %endmacro directive", t.get('line_num'))
                macro_defs[in_macro['name']] = in_macro
                in_macro = None
                continue

            if in_macro:
                in_macro['body'].append(t)
                continue

            if parts[0] in macro_defs:
                m = macro_defs[parts[0]]
                inv_args = parts[1:]
                arg_map = dict(zip(m['args'], inv_args))

                for body_tok in m['body']:
                    new_parts = []
                    for p in body_tok['parts']:
                        new_parts.append(arg_map.get(p, p))
                    filtered.append({
                        'line_num': t.get('line_num'),
                        'raw_line': body_tok.get('raw_line'),
                        'parts': new_parts,
                    })
            else:
                filtered.append(t)

        if in_macro:
            raise AssemblerError(f"Unclosed macro definition for '{in_macro['name']}'")

        return filtered

    def _process_constants_and_data(self, tokens):
        filtered = []
        data_addr = 0

        for t in tokens:
            parts = t['parts']
            first = parts[0].lower()

            if first in ('#define', '@define'):
                if len(parts) >= 3:
                    val_str = parts[2]
                    try:
                        val = int(val_str)
                    except ValueError:
                        val = val_str
                    self.constants[parts[1]] = val
                    self.symbol_table[parts[1]] = {'type': 'constant', 'value': val}
                continue

            if len(parts) >= 3 and parts[1].lower() in ('equ', '.equ'):
                try:
                    val = int(parts[2])
                except ValueError:
                    val = parts[2]
                self.constants[parts[0]] = val
                self.symbol_table[parts[0]] = {'type': 'constant', 'value': val}
                continue

            if first in ('db', '.db', 'dw', '.dw', 'array', '.array'):
                for item in parts[1:]:
                    try:
                        v = int(item)
                    except ValueError:
                        v = item
                    self.data_memory[data_addr] = v
                    data_addr += 1
                continue

            filtered.append(t)

        return filtered
