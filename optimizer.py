import re

class Optimizer:
    """
    Assembly Code AST Optimizer Pass for RoboASM.
    Performs optimization passes:
    1. Constant Folding (e.g. MOV 5 R0 + ADD 3 R0 -> MOV 8 R0)
    2. Redundant Jump Stripping (JMP label when label is right next line)
    3. Dead Code Elimination (instructions unreachable after JMP or HLT without incoming label target)
    4. Nop Removal
    """

    def __init__(self, instructions, labels=None):
        self.instructions = instructions
        self.labels = labels or {}

    def optimize(self):
        insts = [dict(i) for i in self.instructions]
        insts = self._remove_nops(insts)
        insts = self._constant_folding(insts)
        insts = self._remove_redundant_jumps(insts)
        insts = self._remove_dead_code(insts)
        return insts

    def _remove_nops(self, insts):
        return [i for i in insts if i['opcode'] != 'NOP']

    def _constant_folding(self, insts):
        """
        Fold constant MOV followed by arithmetic operations.
        Example: MOV 5 R0 followed by ADD 3 R0 -> MOV 8 R0
        """
        optimized = []
        i = 0
        while i < len(insts):
            curr = insts[i]
            if i + 1 < len(insts):
                nxt = insts[i + 1]
                # Check MOV imm reg followed by ADD imm reg (same reg)
                if curr['opcode'] == 'MOV' and len(curr['args']) == 2:
                    val1, reg1 = curr['args']
                    if isinstance(val1, int) and isinstance(reg1, str) and reg1.startswith('R'):
                        if nxt['opcode'] == 'ADD' and len(nxt['args']) == 2:
                            val2, reg2 = nxt['args']
                            if isinstance(val2, int) and reg2 == reg1:
                                folded = dict(curr)
                                folded['args'] = [val1 + val2, reg1]
                                optimized.append(folded)
                                i += 2
                                continue
                        elif nxt['opcode'] == 'SUB' and len(nxt['args']) == 2:
                            val2, reg2 = nxt['args']
                            if isinstance(val2, int) and reg2 == reg1:
                                folded = dict(curr)
                                folded['args'] = [val1 - val2, reg1]
                                optimized.append(folded)
                                i += 2
                                continue
                        elif nxt['opcode'] == 'MUL' and len(nxt['args']) == 2:
                            val2, reg2 = nxt['args']
                            if isinstance(val2, int) and reg2 == reg1:
                                folded = dict(curr)
                                folded['args'] = [val1 * val2, reg1]
                                optimized.append(folded)
                                i += 2
                                continue
            optimized.append(curr)
            i += 1
        return optimized

    def _remove_redundant_jumps(self, insts):
        """
        Remove JMP N where N is the index of the immediately following instruction.
        """
        optimized = []
        for idx, inst in enumerate(insts):
            if inst['opcode'] == 'JMP' and len(inst['args']) == 1:
                target = inst['args'][0]
                if isinstance(target, int) and target == idx + 1:
                    # Skip redundant jump to next line
                    continue
            optimized.append(inst)
        return optimized

    def _remove_dead_code(self, insts):
        """
        Remove instructions following an unconditional JMP or HLT
        if no known label jumps to them.
        """
        if not self.labels:
            return insts

        target_indices = set(self.labels.values())
        optimized = []
        unreachable = False

        for idx, inst in enumerate(insts):
            if idx in target_indices:
                unreachable = False

            if not unreachable:
                optimized.append(inst)

            if inst['opcode'] in ('JMP', 'HLT'):
                # Check if target is not immediately next
                if inst['opcode'] == 'JMP' and len(inst['args']) == 1 and inst['args'][0] == idx + 1:
                    pass
                else:
                    unreachable = True

        return optimized
