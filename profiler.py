class Profiler:
    """
    Performance Profiler for RoboASM assembly code execution.
    Analyzes opcode frequencies, cycle breakdowns, and RAM heatmaps.
    """

    def __init__(self, instructions):
        self.instructions = instructions
        self.opcode_counts = {}
        self.ram_accesses = {}
        self.total_cycles = 0

    def record_step(self, robot, opcode, args):
        self.total_cycles += 1
        self.opcode_counts[opcode] = self.opcode_counts.get(opcode, 0) + 1

        if opcode in ('LOAD', 'STORE') and len(args) >= 2:
            addr = args[0] if isinstance(args[0], int) else args[1]
            if isinstance(addr, int):
                self.ram_accesses[addr] = self.ram_accesses.get(addr, 0) + 1

    def get_summary(self):
        return {
            'total_cycles': self.total_cycles,
            'opcode_breakdown': self.opcode_counts,
            'ram_heatmap': self.ram_accesses
        }
