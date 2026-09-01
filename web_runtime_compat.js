(() => {
  'use strict';

  // Compatibility fixes for the legacy browser VM.  Python remains the
  // authoritative runtime; this shim keeps the interactive VM aligned while
  // the embedded runtime is incrementally retired/refactored.
  if (typeof Robot === 'undefined' || !Robot.prototype || !Robot.prototype.step) {
    throw new Error('RoboASM Web runtime compatibility shim could not find Robot.step');
  }
  if (Robot.prototype.step.__roboasmCompatWrapped) return;

  const originalStep = Robot.prototype.step;

  function opcodeOf(instruction) {
    return String((instruction && (instruction.opcode || instruction.op)) || '').toUpperCase();
  }

  function argsOf(instruction) {
    return instruction && Array.isArray(instruction.args) ? instruction.args : [];
  }

  function fail(robot, message) {
    robot.halted = true;
    robot.error = message;
    throw new Error(message);
  }

  function toExactBigInt(robot, value, context) {
    if (!Number.isSafeInteger(value)) {
      fail(robot, `${context} requires a safe integer in the Web VM`);
    }
    return BigInt(value);
  }

  function fromExactBigInt(robot, value, context) {
    const number = Number(value);
    if (!Number.isSafeInteger(number) || BigInt(number) !== value) {
      fail(robot, `${context} result exceeds the Web VM safe-integer range`);
    }
    return number;
  }

  function pythonModulo(dividend, divisor) {
    return dividend - Math.floor(dividend / divisor) * divisor;
  }

  function executeWideBitwise(robot, opcode, args) {
    if (opcode === 'NOT') {
      const value = toExactBigInt(robot, robot.getVal(args[0]), 'NOT');
      robot.setVal(args[0], fromExactBigInt(robot, ~value, 'NOT'));
      return true;
    }

    if (opcode === 'SHL' || opcode === 'SHR') {
      const value = toExactBigInt(robot, robot.getVal(args[0]), opcode);
      const bitsNumber = robot.getVal(args[1]);
      if (!Number.isSafeInteger(bitsNumber) || bitsNumber < 0) {
        fail(robot, `${opcode} shift count must be a non-negative safe integer`);
      }
      const bits = BigInt(bitsNumber);
      const result = opcode === 'SHL' ? value << bits : value >> bits;
      robot.setVal(args[0], fromExactBigInt(robot, result, opcode));
      return true;
    }

    if (opcode === 'AND' || opcode === 'OR' || opcode === 'XOR') {
      const left = toExactBigInt(robot, robot.getVal(args[0]), opcode);
      const right = toExactBigInt(robot, robot.getVal(args[1]), opcode);
      let result;
      if (opcode === 'AND') result = right & left;
      else if (opcode === 'OR') result = right | left;
      else result = right ^ left;
      robot.setVal(args[1], fromExactBigInt(robot, result, opcode));
      return true;
    }

    return false;
  }

  function compatibleStep(instructions, grid, vmContext) {
    if (this.halted || this.pc >= instructions.length) {
      return originalStep.call(this, instructions, grid, vmContext);
    }

    const instruction = instructions[this.pc];
    const opcode = opcodeOf(instruction);
    const args = argsOf(instruction);

    // The embedded implementation used `(this.x,this.y) in grid.inboxes`,
    // which invokes JavaScript's comma operator and misses empty inboxes.  The
    // Python VM treats a PICK from an empty inbox as a runtime fault.
    if (opcode === 'PICK') {
      const key = `${this.x},${this.y}`;
      if (Object.prototype.hasOwnProperty.call(grid.inboxes || {}, key)
          && grid.inboxes[key].length === 0) {
        fail(this, 'Inbox is empty');
      }
    }

    // Python intentionally keeps NOOP as a backwards-compatible NOP alias.
    if (opcode === 'NOOP') {
      this.pc += 1;
      return;
    }

    // JavaScript `%` uses truncating remainder while Python `%` follows floor
    // division.  Match Python so negative operands have identical semantics.
    if (opcode === 'MOD') {
      const divisor = this.getVal(args[0]);
      const dividend = this.getVal(args[1]);
      if (divisor === 0) fail(this, 'Modulo by zero');
      this.setVal(args[1], pythonModulo(dividend, divisor));
      this.pc += 1;
      return;
    }

    // Native JS bitwise operators silently coerce Numbers to signed 32-bit.
    // RoboASM/Python integers do not.  BigInt preserves exact semantics for
    // every value the browser can still represent exactly as a Number.
    if (executeWideBitwise(this, opcode, args)) {
      this.pc += 1;
      return;
    }

    return originalStep.call(this, instructions, grid, vmContext);
  }

  compatibleStep.__roboasmCompatWrapped = true;
  compatibleStep.__roboasmOriginalStep = originalStep;
  Robot.prototype.step = compatibleStep;

  globalThis.ROBOASM_WEB_RUNTIME_COMPAT = Object.freeze({
    version: 1,
    fixes: ['empty-inbox-pick', 'noop-alias', 'python-modulo', 'wide-bitwise'],
  });
})();
