"""Central RoboASM instruction-set metadata and operand validation.

Keeping opcode and operand metadata in one place prevents the assembler and VM
from silently accepting different instruction shapes as the language evolves.
"""

REGISTER_NAMES = frozenset({'R0', 'R1', 'R2', 'R3'})
READABLE_NAMES = frozenset(set(REGISTER_NAMES) | {'INV', 'X', 'Y'})
WRITABLE_NAMES = frozenset(set(REGISTER_NAMES) | {'INV'})
TURN_DIRECTIONS = frozenset({'L', 'LEFT', 'R', 'RIGHT'})

VALUE = 'value'
WRITABLE = 'writable'
ADDRESS = 'address'
TARGET = 'target'
TURN = 'turn'

# Operand schemas describe the values the VM can actually consume.  ``value``
# and ``address`` are intentionally equivalent today because both are resolved
# through Robot.get_val(); separate names leave room for a future address type.
INSTRUCTION_SET = {
    # Data movement / arithmetic
    'MOV': (VALUE, WRITABLE),
    'ADD': (VALUE, WRITABLE),
    'SUB': (VALUE, WRITABLE),
    'MUL': (VALUE, WRITABLE),
    'DIV': (VALUE, WRITABLE),
    'MOD': (VALUE, WRITABLE),
    'CMP': (VALUE, VALUE),

    # Stack / memory
    'PUSH': (VALUE,),
    'POP': (WRITABLE,),
    'LOAD': (ADDRESS, WRITABLE),
    'STORE': (VALUE, ADDRESS),

    # Bitwise
    'AND': (VALUE, WRITABLE),
    'OR': (VALUE, WRITABLE),
    'XOR': (VALUE, WRITABLE),
    'NOT': (WRITABLE,),
    'SHL': (WRITABLE, VALUE),
    'SHR': (WRITABLE, VALUE),

    # Extended math
    'SWAP': (WRITABLE, WRITABLE),
    'INC': (WRITABLE,),
    'DEC': (WRITABLE,),
    'MIN': (VALUE, WRITABLE),
    'MAX': (VALUE, WRITABLE),
    'ABS': (WRITABLE,),

    # Inter-robot messaging
    'SEND': (VALUE,),
    'RECV': (WRITABLE,),

    # Control flow
    'JMP': (TARGET,),
    'JEQ': (TARGET,),
    'JNE': (TARGET,),
    'JLT': (TARGET,),
    'JGT': (TARGET,),
    'CALL': (TARGET,),
    'RET': (),

    # Grid / robot operations
    'MOVE': (),
    'TURN': (TURN,),
    'PICK': (),
    'DROP': (),
    'HLT': (),
    'NOP': (),
    'NOOP': (),  # Backward-compatible alias used by bundled solutions.
}

OPCODE_ARITY = {opcode: len(schema) for opcode, schema in INSTRUCTION_SET.items()}


def get_opcode_arity(opcode):
    """Return the required argument count for *opcode*, or ``None`` if unknown."""
    if not isinstance(opcode, str):
        return None
    return OPCODE_ARITY.get(opcode.upper())


def get_operand_schema(opcode):
    """Return the operand schema tuple for *opcode*, or ``None`` if unknown."""
    if not isinstance(opcode, str):
        return None
    return INSTRUCTION_SET.get(opcode.upper())


def format_arity_error(opcode, expected, actual):
    noun = 'argument' if expected == 1 else 'arguments'
    return f"Opcode '{opcode}' expects {expected} {noun}, got {actual}"


def _is_value(operand):
    return (
        isinstance(operand, int)
        and not isinstance(operand, bool)
    ) or (
        isinstance(operand, str)
        and operand.upper() in READABLE_NAMES
    )


def _is_writable(operand):
    return isinstance(operand, str) and operand.upper() in WRITABLE_NAMES


def validate_instruction_operands(opcode, args, instruction_count=None):
    """Return ``None`` when operands are valid, otherwise a diagnostic string.

    ``instruction_count`` enables range checking for control-flow targets.  A
    target exactly one past the final instruction is allowed because the VM
    treats ``pc >= len(instructions)`` as a clean halt; this also supports a
    trailing label used as an explicit exit target.
    """
    schema = get_operand_schema(opcode)
    if schema is None:
        return f"Unknown opcode '{opcode}'"
    if len(args) != len(schema):
        return format_arity_error(opcode, len(schema), len(args))

    for index, (kind, operand) in enumerate(zip(schema, args), start=1):
        if kind in (VALUE, ADDRESS):
            if not _is_value(operand):
                return (
                    f"Opcode '{opcode}' argument {index} must be an integer, "
                    f"register, INV, X, or Y; got {operand!r}"
                )
        elif kind == WRITABLE:
            if not _is_writable(operand):
                return (
                    f"Opcode '{opcode}' argument {index} must be writable "
                    f"(R0-R3 or INV); got {operand!r}"
                )
        elif kind == TARGET:
            if not isinstance(operand, int) or isinstance(operand, bool):
                return (
                    f"Opcode '{opcode}' argument {index} must resolve to an "
                    f"instruction address; got {operand!r}"
                )
            if operand < 0:
                return f"Opcode '{opcode}' target cannot be negative; got {operand}"
            if instruction_count is not None and operand > instruction_count:
                return (
                    f"Opcode '{opcode}' target {operand} is outside program range "
                    f"0..{instruction_count}"
                )
        elif kind == TURN:
            if not isinstance(operand, str) or operand.upper() not in TURN_DIRECTIONS:
                return (
                    f"Opcode '{opcode}' argument {index} must be L, LEFT, R, "
                    f"or RIGHT; got {operand!r}"
                )
        else:
            return f"Opcode '{opcode}' uses unsupported operand schema '{kind}'"

    return None
