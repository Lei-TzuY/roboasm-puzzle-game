"""Central RoboASM instruction-set metadata.

Keeping opcode metadata in one place prevents the assembler and VM from silently
accepting different instruction shapes as the language evolves.
"""

OPCODE_ARITY = {
    # Data movement / arithmetic
    'MOV': 2,
    'ADD': 2,
    'SUB': 2,
    'MUL': 2,
    'DIV': 2,
    'MOD': 2,
    'CMP': 2,

    # Stack / memory
    'PUSH': 1,
    'POP': 1,
    'LOAD': 2,
    'STORE': 2,

    # Bitwise
    'AND': 2,
    'OR': 2,
    'XOR': 2,
    'NOT': 1,
    'SHL': 2,
    'SHR': 2,

    # Extended math
    'SWAP': 2,
    'INC': 1,
    'DEC': 1,
    'MIN': 2,
    'MAX': 2,
    'ABS': 1,

    # Inter-robot messaging
    'SEND': 1,
    'RECV': 1,

    # Control flow
    'JMP': 1,
    'JEQ': 1,
    'JNE': 1,
    'JLT': 1,
    'JGT': 1,
    'CALL': 1,
    'RET': 0,

    # Grid / robot operations
    'MOVE': 0,
    'TURN': 1,
    'PICK': 0,
    'DROP': 0,
    'HLT': 0,
    'NOP': 0,
}


def get_opcode_arity(opcode):
    """Return the required argument count for *opcode*, or ``None`` if unknown."""
    if not isinstance(opcode, str):
        return None
    return OPCODE_ARITY.get(opcode.upper())


def format_arity_error(opcode, expected, actual):
    noun = 'argument' if expected == 1 else 'arguments'
    return f"Opcode '{opcode}' expects {expected} {noun}, got {actual}"
