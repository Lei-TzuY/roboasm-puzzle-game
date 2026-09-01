(() => {
  'use strict';

  // Runtime compatibility fixes for the legacy browser VM. Python remains the
  // authoritative runtime; compiler/preprocessor parity lives separately in
  // web_preprocessor.js so the two concerns can evolve independently.
  if (typeof Robot === 'undefined' || !Robot.prototype || !Robot.prototype.step
      || typeof VM === 'undefined') {
    throw new Error('RoboASM Web runtime compatibility shim could not find the embedded runtime');
  }
  if (Robot.prototype.step.__roboasmCompatWrapped) return;

  const originalStep = Robot.prototype.step;
  const OriginalVM = VM;
  const DATA_MEMORY_KEY = '__roboasmDataMemory';

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

  class CompatibleVM extends OriginalVM {
    constructor(instructions, levelDef) {
      super(instructions, levelDef);
      const initialData = instructions && instructions[DATA_MEMORY_KEY]
        ? instructions[DATA_MEMORY_KEY]
        : {};
      this.sharedRam = {...initialData};
      for (const robot of this.robots) robot.ram = this.sharedRam;
    }
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
    // which invokes JavaScript's comma operator and misses empty inboxes. The
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
    // division. Match Python so negative operands have identical semantics.
    if (opcode === 'MOD') {
      const divisor = this.getVal(args[0]);
      const dividend = this.getVal(args[1]);
      if (divisor === 0) fail(this, 'Modulo by zero');
      this.setVal(args[1], pythonModulo(dividend, divisor));
      this.pc += 1;
      return;
    }

    // Native JS bitwise operators silently coerce Numbers to signed 32-bit.
    // RoboASM/Python integers do not. BigInt preserves exact semantics for
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
  VM = CompatibleVM;

  function readIntegerControl(id, label) {
    if (typeof document === 'undefined') return null;
    const input = document.getElementById(id);
    if (!input) return null;
    const value = String(input.value ?? '').trim();
    if (!value) return null;
    if (!/^-?\d+$/.test(value)) throw new Error(`${label} must be an integer`);
    const parsed = Number(value);
    if (!Number.isSafeInteger(parsed)) throw new Error(`${label} is outside the Web safe-integer range`);
    return parsed;
  }

  function checked(id) {
    if (typeof document === 'undefined') return false;
    const input = document.getElementById(id);
    return !!(input && input.checked);
  }

  function buildAdvancedStopSpec(lineBreakpoints, defaultRobotId) {
    const lines = Array.isArray(lineBreakpoints) ? [...lineBreakpoints] : [];
    const conditionalBreakpoints = [];
    const watchpoints = [];

    if (checked('authority-cond-enabled')) {
      const lineNum = readIntegerControl('authority-cond-line', 'Conditional breakpoint line');
      const conditionInput = document.getElementById('authority-cond-expr');
      const condition = String(conditionInput ? conditionInput.value : '').trim();
      if (!Number.isInteger(lineNum) || lineNum < 1) {
        throw new Error('Conditional breakpoint line must be a positive integer');
      }
      if (!condition) throw new Error('Conditional breakpoint expression is required');
      conditionalBreakpoints.push({
        line_num: lineNum,
        condition,
        robot_id: defaultRobotId,
      });
    }

    if (checked('authority-reg-watch-enabled')) {
      const registerInput = document.getElementById('authority-reg-watch-name');
      const name = String(registerInput ? registerInput.value : '').trim().toUpperCase();
      if (!/^R[0-3]$/.test(name)) throw new Error('Register watchpoint must be R0, R1, R2, or R3');
      watchpoints.push({kind: 'register', robot_id: defaultRobotId, name});
    }

    if (checked('authority-ram-watch-enabled')) {
      const address = readIntegerControl('authority-ram-watch-address', 'RAM watchpoint address');
      if (!Number.isInteger(address)) throw new Error('RAM watchpoint address is required');
      watchpoints.push({kind: 'ram', address});
    }

    if (!conditionalBreakpoints.length && !watchpoints.length) return lines;
    return {
      lines,
      conditional_breakpoints: conditionalBreakpoints,
      watchpoints,
    };
  }

  function watchpointMessage(hit) {
    if (!hit) return 'Watchpoint hit';
    const oldValue = hit.old_exists ? JSON.stringify(hit.old_value) : '∅';
    const newValue = hit.new_exists ? JSON.stringify(hit.new_value) : '∅';
    if (hit.kind === 'register') {
      return `Watchpoint ${hit.name} (robot ${hit.robot_id}): ${oldValue} → ${newValue}`;
    }
    return `Watchpoint RAM[${hit.address}]: ${oldValue} → ${newValue}`;
  }

  function installAdvancedStopEditor() {
    if (typeof document === 'undefined') return;
    if (document.getElementById('authority-advanced-stops')) return;
    const panel = document.getElementById('authority-panel');
    if (!panel || typeof panel.appendChild !== 'function') return;

    const holder = document.createElement('div');
    holder.id = 'authority-advanced-stops';
    holder.style.cssText = 'margin-top:10px;padding-top:8px;border-top:1px solid #30363d;color:#8b949e;';
    holder.innerHTML = `
      <details>
        <summary style="cursor:pointer;color:#58a6ff">Advanced Stops · conditional breakpoint / watchpoints</summary>
        <div style="display:grid;grid-template-columns:auto 70px 1fr;gap:6px 8px;align-items:center;margin-top:8px">
          <label><input id="authority-cond-enabled" type="checkbox"> Conditional</label>
          <input id="authority-cond-line" type="number" min="1" placeholder="line" title="Source line">
          <input id="authority-cond-expr" type="text" placeholder="R0 == 3 and RAM[0] != 7" title="Safe Python-like debugger condition">
          <label><input id="authority-reg-watch-enabled" type="checkbox"> Register</label>
          <select id="authority-reg-watch-name"><option>R0</option><option>R1</option><option>R2</option><option>R3</option></select>
          <span>Stop after the selected robot's register changes.</span>
          <label><input id="authority-ram-watch-enabled" type="checkbox"> RAM</label>
          <input id="authority-ram-watch-address" type="number" value="0" placeholder="addr">
          <span>Stop after shared RAM at this address changes.</span>
        </div>
        <div style="margin-top:6px;color:#6e7681">Conditions are evaluated only by the authoritative Python debugger. Step Back restores the pre-watchpoint checkpoint.</div>
      </details>`;
    panel.appendChild(holder);
  }

  const originalFetch = typeof globalThis.fetch === 'function'
    ? globalThis.fetch.bind(globalThis)
    : null;
  if (originalFetch) {
    globalThis.fetch = async function roboasmAdvancedStopFetch(url, options = {}) {
      const path = typeof url === 'string' ? url : String(url && url.url ? url.url : url);
      let nextOptions = options;
      if (/\/api\/debug\/sessions\/[^/]+\/run(?:\?|$)/.test(path)
          && String(options.method || 'GET').toUpperCase() === 'POST'
          && typeof options.body === 'string') {
        let body;
        try {
          body = JSON.parse(options.body);
        } catch (_) {
          body = null;
        }
        if (body && Array.isArray(body.breakpoint_lines)) {
          body.breakpoint_lines = buildAdvancedStopSpec(
            body.breakpoint_lines,
            Number.isInteger(body.breakpoint_robot_id) ? body.breakpoint_robot_id : 0,
          );
          nextOptions = {...options, body: JSON.stringify(body)};
        }
      }

      const response = await originalFetch(url, nextOptions);
      if (!/\/api\/debug\/sessions\/[^/]+\/run(?:\?|$)/.test(path)
          || String(nextOptions.method || 'GET').toUpperCase() !== 'POST') {
        return response;
      }

      const payload = await response.json();
      const execution = payload && payload.execution ? payload.execution : {};
      globalThis.ROBOASM_ADVANCED_LAST_HIT = execution.stopped_by_breakpoint
        ? execution.breakpoint
        : (execution.stopped_by_watchpoint ? execution.watchpoint : null);

      if (execution.stopped_by_watchpoint) {
        if (typeof globalThis.stopAuto === 'function') globalThis.stopAuto();
        if (typeof globalThis.setMsg === 'function') {
          globalThis.setMsg(watchpointMessage(execution.watchpoint), 'msg-err');
        }
      }

      return {
        ok: response.ok,
        status: response.status,
        async json() { return payload; },
      };
    };
  }

  // web_authority.js is loaded immediately after this shim. Defer UI/message
  // decoration until that script has installed the authoritative panel and
  // rebound the global controls.
  if (typeof setTimeout === 'function') {
    setTimeout(() => {
      installAdvancedStopEditor();
      if (typeof globalThis.setMsg === 'function' && !globalThis.setMsg.__roboasmAdvancedWrapped) {
        const originalSetMsg = globalThis.setMsg;
        const wrappedSetMsg = function advancedStopMessage(text, cls) {
          const hit = globalThis.ROBOASM_ADVANCED_LAST_HIT;
          if (hit && hit.kind === 'conditional'
              && typeof text === 'string' && text.startsWith('Breakpoint hit on line')) {
            text = `Conditional breakpoint line ${hit.line_num}: ${hit.condition}`;
          }
          return originalSetMsg(text, cls);
        };
        wrappedSetMsg.__roboasmAdvancedWrapped = true;
        globalThis.setMsg = wrappedSetMsg;
      }
    }, 0);
  }

  globalThis.ROBOASM_ADVANCED_STOPS = Object.freeze({
    buildStopSpec: buildAdvancedStopSpec,
    watchpointMessage,
    installEditor: installAdvancedStopEditor,
  });

  globalThis.ROBOASM_WEB_RUNTIME_COMPAT = Object.freeze({
    version: 4,
    fixes: [
      'initial-data-memory',
      'empty-inbox-pick',
      'noop-alias',
      'python-modulo',
      'wide-bitwise',
      'advanced-debug-stops',
    ],
  });
})();
