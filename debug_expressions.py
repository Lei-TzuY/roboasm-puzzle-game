"""Safe expression support for authoritative debugger conditions."""

import ast


class DebugExpressionError(ValueError):
    """Raised when a debugger expression is invalid or unsafe."""


_ALLOWED_NAMES = {
    'R0', 'R1', 'R2', 'R3',
    'INV', 'X', 'Y', 'PC', 'CYCLES',
    'ZERO', 'NEGATIVE', 'RAM',
}
_ALLOWED_BINOPS = (
    ast.Add, ast.Sub, ast.Mult, ast.FloorDiv, ast.Mod,
    ast.BitAnd, ast.BitOr, ast.BitXor, ast.LShift, ast.RShift,
)
_ALLOWED_UNARYOPS = (ast.Not, ast.USub, ast.UAdd, ast.Invert)
_ALLOWED_BOOLOPS = (ast.And, ast.Or)
_ALLOWED_CMPOPS = (
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE,
    ast.Is, ast.IsNot,
)


def _constant_int(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, int) \
            and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub) \
            and isinstance(node.operand, ast.Constant) \
            and isinstance(node.operand.value, int) \
            and not isinstance(node.operand.value, bool):
        return -node.operand.value
    raise DebugExpressionError('RAM index must be an integer literal')


def _validate(node):
    if isinstance(node, ast.Expression):
        _validate(node.body)
        return
    if isinstance(node, ast.Constant):
        if node.value is None or isinstance(node.value, (bool, int)):
            return
        raise DebugExpressionError('Only integer, boolean, and None literals are allowed')
    if isinstance(node, ast.Name):
        if node.id not in _ALLOWED_NAMES:
            raise DebugExpressionError(f"Unknown debugger name '{node.id}'")
        return
    if isinstance(node, ast.Subscript):
        if not isinstance(node.value, ast.Name) or node.value.id != 'RAM':
            raise DebugExpressionError('Only RAM[integer] subscripts are allowed')
        _constant_int(node.slice)
        return
    if isinstance(node, ast.BinOp):
        if not isinstance(node.op, _ALLOWED_BINOPS):
            raise DebugExpressionError('Unsupported arithmetic operator')
        _validate(node.left)
        _validate(node.right)
        return
    if isinstance(node, ast.UnaryOp):
        if not isinstance(node.op, _ALLOWED_UNARYOPS):
            raise DebugExpressionError('Unsupported unary operator')
        _validate(node.operand)
        return
    if isinstance(node, ast.BoolOp):
        if not isinstance(node.op, _ALLOWED_BOOLOPS):
            raise DebugExpressionError('Unsupported boolean operator')
        for value in node.values:
            _validate(value)
        return
    if isinstance(node, ast.Compare):
        _validate(node.left)
        for op in node.ops:
            if not isinstance(op, _ALLOWED_CMPOPS):
                raise DebugExpressionError('Unsupported comparison operator')
        for comparator in node.comparators:
            _validate(comparator)
        return
    raise DebugExpressionError(
        f"Unsupported debugger expression element: {type(node).__name__}"
    )


def compile_debug_expression(source):
    """Parse and validate a bounded debugger expression without using eval()."""
    if not isinstance(source, str) or not source.strip():
        raise DebugExpressionError('condition must be a non-empty string')
    source = source.strip()
    if len(source) > 256:
        raise DebugExpressionError('condition must be at most 256 characters')
    try:
        tree = ast.parse(source, mode='eval')
    except SyntaxError as exc:
        raise DebugExpressionError(f'Invalid debugger condition: {exc.msg}') from exc
    _validate(tree)
    return tree.body


def _eval(node, context):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        return context[node.id]
    if isinstance(node, ast.Subscript):
        return context['RAM'].get(_constant_int(node.slice))
    if isinstance(node, ast.UnaryOp):
        value = _eval(node.operand, context)
        if isinstance(node.op, ast.Not):
            return not value
        if isinstance(node.op, ast.USub):
            return -value
        if isinstance(node.op, ast.UAdd):
            return +value
        if isinstance(node.op, ast.Invert):
            return ~value
    if isinstance(node, ast.BinOp):
        left = _eval(node.left, context)
        right = _eval(node.right, context)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.FloorDiv):
            return left // right
        if isinstance(node.op, ast.Mod):
            return left % right
        if isinstance(node.op, ast.BitAnd):
            return left & right
        if isinstance(node.op, ast.BitOr):
            return left | right
        if isinstance(node.op, ast.BitXor):
            return left ^ right
        if isinstance(node.op, ast.LShift):
            return left << right
        if isinstance(node.op, ast.RShift):
            return left >> right
    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            result = True
            for value in node.values:
                result = _eval(value, context)
                if not result:
                    return result
            return result
        result = False
        for value in node.values:
            result = _eval(value, context)
            if result:
                return result
        return result
    if isinstance(node, ast.Compare):
        left = _eval(node.left, context)
        for op, comparator in zip(node.ops, node.comparators):
            right = _eval(comparator, context)
            if isinstance(op, ast.Eq):
                ok = left == right
            elif isinstance(op, ast.NotEq):
                ok = left != right
            elif isinstance(op, ast.Lt):
                ok = left < right
            elif isinstance(op, ast.LtE):
                ok = left <= right
            elif isinstance(op, ast.Gt):
                ok = left > right
            elif isinstance(op, ast.GtE):
                ok = left >= right
            elif isinstance(op, ast.Is):
                ok = left is right
            elif isinstance(op, ast.IsNot):
                ok = left is not right
            else:
                raise DebugExpressionError('Unsupported comparison operator')
            if not ok:
                return False
            left = right
        return True
    raise DebugExpressionError('Unsupported debugger expression')


def evaluate_debug_expression(compiled, context):
    """Evaluate a validated expression against a debugger context."""
    try:
        return _eval(compiled, context)
    except DebugExpressionError:
        raise
    except Exception as exc:
        raise DebugExpressionError(
            f'Conditional breakpoint evaluation failed: {exc}'
        ) from exc
