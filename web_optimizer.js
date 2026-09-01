(() => {
  'use strict';

  const CONTROL_FLOW = new Set(['JMP', 'JEQ', 'JNE', 'JLT', 'JGT', 'CALL']);
  const CONDITIONAL = new Set(['JEQ', 'JNE', 'JLT', 'JGT']);

  function cloneInstruction(inst) {
    return {...inst, args: Array.isArray(inst.args) ? [...inst.args] : []};
  }

  function sameInstructions(left, right) {
    if (left.length !== right.length) return false;
    for (let i = 0; i < left.length; i += 1) {
      const a = left[i];
      const b = right[i];
      if (a.opcode !== b.opcode || a.line_num !== b.line_num) return false;
      if (a.args.length !== b.args.length) return false;
      for (let j = 0; j < a.args.length; j += 1) {
        if (a.args[j] !== b.args[j]) return false;
      }
    }
    return true;
  }

  function sameLabels(left, right) {
    const leftKeys = Object.keys(left || {}).sort();
    const rightKeys = Object.keys(right || {}).sort();
    if (leftKeys.length !== rightKeys.length) return false;
    return leftKeys.every((key, index) => (
      key === rightKeys[index] && left[key] === right[key]
    ));
  }

  function entryTargets(insts, labels) {
    const targets = new Set();
    for (const value of Object.values(labels || {})) {
      if (Number.isInteger(value) && value >= 0 && value <= insts.length) targets.add(value);
    }
    for (const inst of insts) {
      if (!CONTROL_FLOW.has(inst.opcode) || !inst.args || !Number.isInteger(inst.args[0])) continue;
      if (inst.args[0] >= 0 && inst.args[0] <= insts.length) targets.add(inst.args[0]);
    }
    return targets;
  }

  function compact(insts, labels, entries) {
    const direct = new Map();
    entries.forEach(([oldIndexes], newIndex) => {
      oldIndexes.forEach(oldIndex => direct.set(oldIndex, newIndex));
    });

    const indexMap = new Map([[insts.length, entries.length]]);
    let nextIndex = entries.length;
    for (let oldIndex = insts.length - 1; oldIndex >= 0; oldIndex -= 1) {
      if (direct.has(oldIndex)) nextIndex = direct.get(oldIndex);
      indexMap.set(oldIndex, nextIndex);
    }

    const rebuilt = entries.map(([, inst]) => {
      const copied = cloneInstruction(inst);
      if (CONTROL_FLOW.has(copied.opcode) && Number.isInteger(copied.args[0]) && indexMap.has(copied.args[0])) {
        copied.args[0] = indexMap.get(copied.args[0]);
      }
      return copied;
    });

    const rebuiltLabels = {};
    for (const [name, value] of Object.entries(labels || {})) {
      rebuiltLabels[name] = indexMap.has(value) ? indexMap.get(value) : value;
    }
    return {instructions: rebuilt, labels: rebuiltLabels};
  }

  function removeNops(insts, labels) {
    const entries = [];
    insts.forEach((inst, idx) => {
      if (inst.opcode !== 'NOP' && inst.opcode !== 'NOOP') entries.push([[idx], inst]);
    });
    return compact(insts, labels, entries);
  }

  function constantFold(insts, labels) {
    const protectedTargets = entryTargets(insts, labels);
    const entries = [];
    let i = 0;
    while (i < insts.length) {
      const curr = insts[i];
      const nxt = i + 1 < insts.length ? insts[i + 1] : null;
      if (nxt && !protectedTargets.has(i + 1)
          && curr.opcode === 'MOV' && curr.args.length === 2
          && Number.isInteger(curr.args[0])
          && typeof curr.args[1] === 'string' && curr.args[1].startsWith('R')
          && ['ADD', 'SUB', 'MUL'].includes(nxt.opcode) && nxt.args.length === 2
          && Number.isInteger(nxt.args[0]) && nxt.args[1] === curr.args[1]) {
        let value = curr.args[0];
        if (nxt.opcode === 'ADD') value += nxt.args[0];
        else if (nxt.opcode === 'SUB') value -= nxt.args[0];
        else value *= nxt.args[0];
        const folded = cloneInstruction(curr);
        folded.args = [value, curr.args[1]];
        entries.push([[i, i + 1], folded]);
        i += 2;
        continue;
      }
      entries.push([[i], curr]);
      i += 1;
    }
    return compact(insts, labels, entries);
  }

  function removeRedundantJumps(insts, labels) {
    const entries = [];
    insts.forEach((inst, idx) => {
      if (inst.opcode === 'JMP' && inst.args.length === 1
          && Number.isInteger(inst.args[0]) && inst.args[0] === idx + 1) return;
      entries.push([[idx], inst]);
    });
    return compact(insts, labels, entries);
  }

  function successors(insts, idx) {
    const inst = insts[idx];
    const next = idx + 1;
    const out = [];
    const addTarget = () => {
      const target = inst.args && inst.args[0];
      if (Number.isInteger(target) && target >= 0 && target < insts.length) out.push(target);
    };

    if (inst.opcode === 'JMP') addTarget();
    else if (CONDITIONAL.has(inst.opcode)) {
      addTarget();
      if (next < insts.length) out.push(next);
    } else if (inst.opcode === 'CALL') {
      addTarget();
      if (next < insts.length) out.push(next);
    } else if (inst.opcode !== 'HLT' && inst.opcode !== 'RET' && next < insts.length) {
      out.push(next);
    }
    return out;
  }

  function removeDeadCode(insts, labels) {
    if (insts.length === 0) return {instructions: insts, labels: {...labels}};
    const roots = new Set([0]);
    for (const value of Object.values(labels || {})) {
      if (Number.isInteger(value) && value >= 0 && value < insts.length) roots.add(value);
    }

    const reachable = new Set();
    const pending = [...roots];
    while (pending.length) {
      const idx = pending.pop();
      if (reachable.has(idx) || idx < 0 || idx >= insts.length) continue;
      reachable.add(idx);
      pending.push(...successors(insts, idx));
    }

    const entries = [];
    insts.forEach((inst, idx) => {
      if (reachable.has(idx)) entries.push([[idx], inst]);
    });
    return compact(insts, labels, entries);
  }

  function optimizeRoboASM(instructions, labels = {}) {
    let state = {
      instructions: instructions.map(cloneInstruction),
      labels: {...labels},
    };
    const maxRounds = Math.max(1, 2 * state.instructions.length + 2);

    for (let round = 0; round < maxRounds; round += 1) {
      const beforeInstructions = state.instructions.map(cloneInstruction);
      const beforeLabels = {...state.labels};

      state = removeNops(state.instructions, state.labels);
      state = constantFold(state.instructions, state.labels);
      state = removeRedundantJumps(state.instructions, state.labels);
      state = removeDeadCode(state.instructions, state.labels);

      if (sameInstructions(beforeInstructions, state.instructions)
          && sameLabels(beforeLabels, state.labels)) {
        return state;
      }
    }

    throw new Error(`Web optimizer did not converge after ${maxRounds} rounds`);
  }

  globalThis.optimizeRoboASM = optimizeRoboASM;
  globalThis.ROBOASM_WEB_OPTIMIZER = Object.freeze({
    version: 2,
    passes: ['nop-removal', 'constant-folding', 'redundant-jump-removal', 'cfg-dead-code'],
    controlFlowSafe: true,
    fixedPoint: true,
  });
})();
