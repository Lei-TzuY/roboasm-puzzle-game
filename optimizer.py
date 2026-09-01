CONTROL_FLOW_OPCODES = {'JMP', 'JEQ', 'JNE', 'JLT', 'JGT', 'CALL'}
CONDITIONAL_JUMPS = {'JEQ', 'JNE', 'JLT', 'JGT'}


class Optimizer:
    """Control-flow-safe optimization passes for resolved RoboASM bytecode.

    Every pass that changes instruction indexes rebuilds numeric branch/call
    targets and label indexes. Constant folding is deliberately blocked across
    a secondary instruction that is itself an entry target.
    """

    def __init__(self, instructions, labels=None):
        self.instructions = instructions
        self.labels = dict(labels or {})

    @staticmethod
    def _copy_instruction(inst):
        copied = dict(inst)
        copied['args'] = list(inst.get('args', []))
        return copied

    def optimize(self):
        insts = [self._copy_instruction(i) for i in self.instructions]
        labels = dict(self.labels)

        insts, labels = self._remove_nops(insts, labels)
        insts, labels = self._constant_folding(insts, labels)
        insts, labels = self._remove_redundant_jumps(insts, labels)
        insts, labels = self._remove_dead_code(insts, labels)

        self.labels = labels
        return insts

    @staticmethod
    def _entry_targets(insts, labels):
        targets = {
            value for value in labels.values()
            if isinstance(value, int) and 0 <= value <= len(insts)
        }
        for inst in insts:
            if inst.get('opcode') not in CONTROL_FLOW_OPCODES:
                continue
            args = inst.get('args', [])
            if args and isinstance(args[0], int) and 0 <= args[0] <= len(insts):
                targets.add(args[0])
        return targets

    def _compact(self, insts, labels, entries):
        """Compact instructions and remap all index-bearing metadata.

        ``entries`` contains ``(old_indices, instruction)`` pairs. Removed
        indexes map to the next surviving instruction (or program end), which
        is semantics-preserving for removed NOPs/redundant jumps/unreachable
        code. Folding may represent two old indexes with one instruction, but
        the second index is never allowed to be an entry target.
        """
        old_count = len(insts)
        direct = {}
        for new_index, (old_indices, _) in enumerate(entries):
            for old_index in old_indices:
                direct[old_index] = new_index

        index_map = {old_count: len(entries)}
        next_index = len(entries)
        for old_index in range(old_count - 1, -1, -1):
            if old_index in direct:
                next_index = direct[old_index]
            index_map[old_index] = next_index

        rebuilt = []
        for _, inst in entries:
            copied = self._copy_instruction(inst)
            if copied.get('opcode') in CONTROL_FLOW_OPCODES:
                args = copied.get('args', [])
                if args and isinstance(args[0], int) and args[0] in index_map:
                    args[0] = index_map[args[0]]
            rebuilt.append(copied)

        rebuilt_labels = {
            name: index_map.get(value, value)
            for name, value in labels.items()
        }
        return rebuilt, rebuilt_labels

    def _remove_nops(self, insts, labels):
        entries = [
            ((idx,), inst)
            for idx, inst in enumerate(insts)
            if inst.get('opcode') not in ('NOP', 'NOOP')
        ]
        return self._compact(insts, labels, entries)

    def _constant_folding(self, insts, labels):
        protected = self._entry_targets(insts, labels)
        entries = []
        i = 0

        while i < len(insts):
            curr = insts[i]
            if i + 1 < len(insts) and (i + 1) not in protected:
                nxt = insts[i + 1]
                if curr.get('opcode') == 'MOV' and len(curr.get('args', [])) == 2:
                    val1, reg1 = curr['args']
                    if isinstance(val1, int) and not isinstance(val1, bool) \
                            and isinstance(reg1, str) and reg1.startswith('R'):
                        if nxt.get('opcode') in ('ADD', 'SUB', 'MUL') \
                                and len(nxt.get('args', [])) == 2:
                            val2, reg2 = nxt['args']
                            if isinstance(val2, int) and not isinstance(val2, bool) \
                                    and reg2 == reg1:
                                if nxt['opcode'] == 'ADD':
                                    value = val1 + val2
                                elif nxt['opcode'] == 'SUB':
                                    value = val1 - val2
                                else:
                                    value = val1 * val2
                                folded = self._copy_instruction(curr)
                                folded['args'] = [value, reg1]
                                entries.append(((i, i + 1), folded))
                                i += 2
                                continue

            entries.append(((i,), curr))
            i += 1

        return self._compact(insts, labels, entries)

    def _remove_redundant_jumps(self, insts, labels):
        entries = []
        for idx, inst in enumerate(insts):
            args = inst.get('args', [])
            if inst.get('opcode') == 'JMP' and len(args) == 1 \
                    and isinstance(args[0], int) and args[0] == idx + 1:
                continue
            entries.append(((idx,), inst))
        return self._compact(insts, labels, entries)

    @staticmethod
    def _successors(insts, idx):
        inst = insts[idx]
        opcode = inst.get('opcode')
        args = inst.get('args', [])
        next_index = idx + 1
        successors = []

        def add_target():
            if args and isinstance(args[0], int) and 0 <= args[0] < len(insts):
                successors.append(args[0])

        if opcode == 'JMP':
            add_target()
        elif opcode in CONDITIONAL_JUMPS:
            add_target()
            if next_index < len(insts):
                successors.append(next_index)
        elif opcode == 'CALL':
            # The call target executes, and the following instruction is a
            # potential continuation after RET.
            add_target()
            if next_index < len(insts):
                successors.append(next_index)
        elif opcode in ('HLT', 'RET'):
            pass
        elif next_index < len(insts):
            successors.append(next_index)

        return successors

    def _remove_dead_code(self, insts, labels):
        if not insts:
            return insts, labels

        # Preserve named entry points conservatively, even when no current
        # instruction references them. This keeps optimized symbol/debug entry
        # points usable while still deleting genuinely unreachable fallthrough.
        roots = {0}
        roots.update(
            value for value in labels.values()
            if isinstance(value, int) and 0 <= value < len(insts)
        )

        reachable = set()
        pending = list(roots)
        while pending:
            idx = pending.pop()
            if idx in reachable or not (0 <= idx < len(insts)):
                continue
            reachable.add(idx)
            pending.extend(self._successors(insts, idx))

        entries = [
            ((idx,), inst)
            for idx, inst in enumerate(insts)
            if idx in reachable
        ]
        return self._compact(insts, labels, entries)
