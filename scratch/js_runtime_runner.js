#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');
const nodeVm = require('vm');

const ROOT_DIR = path.resolve(__dirname, '..');
const WEB_UI_PATH = path.join(ROOT_DIR, 'web_ui.html');
const WEB_OPTIMIZER_PATH = path.join(ROOT_DIR, 'web_optimizer.js');
const WEB_PREPROCESSOR_PATH = path.join(ROOT_DIR, 'web_preprocessor.js');
const WEB_COMPAT_PATH = path.join(ROOT_DIR, 'web_runtime_compat.js');
const RUNTIME_START = 'function lex(src)';
const RUNTIME_END = '// State & History Stack for Breakpoints & Step Back';

function collectIncludeSources(rootDir) {
  const result = {};
  function walk(dir) {
    for (const entry of fs.readdirSync(dir, {withFileTypes: true})) {
      if (entry.name === '.git' || entry.name === '__pycache__' || entry.name === '.pytest_cache') continue;
      const absolute = path.join(dir, entry.name);
      if (entry.isDirectory()) { walk(absolute); continue; }
      if (!entry.isFile() || path.extname(entry.name).toLowerCase() !== '.asm') continue;
      const relative = path.relative(rootDir, absolute).split(path.sep).join('/');
      result[relative] = fs.readFileSync(absolute, 'utf8');
    }
  }
  walk(rootDir);
  return result;
}

function loadEmbeddedRuntime() {
  const html = fs.readFileSync(WEB_UI_PATH, 'utf8');
  const start = html.indexOf(RUNTIME_START);
  const end = html.indexOf(RUNTIME_END, start);
  if (start < 0 || end < 0 || end <= start) throw new Error('Could not locate embedded Web IDE runtime in web_ui.html');

  const sandbox = {
    console,
    playAudioSynth: () => {},
    ROBOASM_WEB_INCLUDE_SOURCES: collectIncludeSources(ROOT_DIR),
  };
  sandbox.globalThis = sandbox;
  nodeVm.createContext(sandbox);
  nodeVm.runInContext(html.slice(start, end), sandbox, {filename: 'web_ui.runtime.js'});

  nodeVm.runInContext(fs.readFileSync(WEB_OPTIMIZER_PATH, 'utf8'), sandbox, {filename: 'web_optimizer.js'});
  nodeVm.runInContext(fs.readFileSync(WEB_PREPROCESSOR_PATH, 'utf8'), sandbox, {filename: 'web_preprocessor.js'});
  nodeVm.runInContext(fs.readFileSync(WEB_COMPAT_PATH, 'utf8'), sandbox, {filename: 'web_runtime_compat.js'});

  nodeVm.runInContext(
    'globalThis.__roboasmRuntime = { lex, assemble, Grid, Robot, VM };',
    sandbox,
    {filename: 'web_ui.runtime.export.js'},
  );
  return sandbox.__roboasmRuntime;
}

function parseCoord(key) {
  const [x, y] = String(key).split(',').map(Number);
  return {x, y};
}

function cloneJson(value) {
  if (value === undefined) return null;
  return JSON.parse(JSON.stringify(value));
}

function coordEntries(mapping, valueKey) {
  return Object.entries(mapping || {})
    .map(([key, value]) => ({...parseCoord(key), [valueKey]: cloneJson(value)}))
    .sort((a, b) => a.x - b.x || a.y - b.y);
}

function sortObject(mapping) {
  const result = {};
  for (const key of Object.keys(mapping || {}).sort((a, b) => Number(a) - Number(b) || a.localeCompare(b))) {
    result[String(key)] = cloneJson(mapping[key]);
  }
  return result;
}

function bytecodeProjection(instructions) {
  return instructions.map(inst => ({opcode: inst.opcode, args: cloneJson(inst.args || [])}));
}

function snapshot(machine) {
  return {
    cycles: machine.cycles,
    halted: !!machine.halted,
    robots: machine.robots.map(robot => ({
      id: robot.id, x: robot.x, y: robot.y, facing: robot.facing,
      inventory: robot.inventory === undefined ? null : robot.inventory,
      registers: sortObject(robot.registers), flags: cloneJson(robot.flags || {}),
      stack: cloneJson(robot.stack || []), pc: robot.pc,
      call_stack: cloneJson(robot.callStack || []), halted: !!robot.halted,
    })),
    ram: sortObject(machine.sharedRam || {}),
    messages: (machine.msgQueue || []).map(message => ({sender_id: message.sender, value: cloneJson(message.val)})),
    grid: {
      width: machine.grid.width,
      height: machine.grid.height,
      items: coordEntries(machine.grid.items, 'value'),
      inboxes: coordEntries(machine.grid.inboxes, 'queue'),
      outboxes: coordEntries(machine.grid.outboxes, 'queue'),
      open_doors: Array.from(machine.grid.openDoors || []).map(parseCoord).sort((a, b) => a.x - b.x || a.y - b.y),
    },
  };
}

function runCase(runtime, testCase) {
  const levelPath = path.join(ROOT_DIR, 'levels', path.basename(testCase.level));
  const levelDef = JSON.parse(fs.readFileSync(levelPath, 'utf8'));
  const code = String(testCase.code || '');
  const maxCycles = Number.isInteger(testCase.max_cycles) ? testCase.max_cycles : 1000;
  const optimize = !!testCase.optimize;

  try {
    const instructions = runtime.assemble(runtime.lex(code), optimize);
    const machine = new runtime.VM(instructions, levelDef);
    const trace = [snapshot(machine)];
    let winResult = machine.checkWin();

    while (!machine.halted && !winResult[0] && machine.cycles < maxCycles) {
      machine.step();
      trace.push(snapshot(machine));
      winResult = machine.checkWin();
    }

    return {
      name: testCase.name,
      status: 'success',
      won: !!winResult[0],
      message: winResult[1],
      cycles: machine.cycles,
      size: instructions.length,
      bytecode: bytecodeProjection(instructions),
      labels: cloneJson(instructions.__roboasmLabels || {}),
      limit_reached: !machine.halted && !winResult[0] && machine.cycles >= maxCycles,
      state: snapshot(machine),
      trace,
    };
  } catch (error) {
    return {name: testCase.name, status: 'error', error: error && error.stack ? error.stack : String(error)};
  }
}

function main() {
  const request = JSON.parse(fs.readFileSync(0, 'utf8') || '{}');
  if (!Array.isArray(request.cases)) throw new Error("Input JSON must contain a 'cases' array");
  const runtime = loadEmbeddedRuntime();
  process.stdout.write(JSON.stringify({results: request.cases.map(testCase => runCase(runtime, testCase))}));
}

try { main(); }
catch (error) {
  process.stderr.write(`${error && error.stack ? error.stack : error}\n`);
  process.exitCode = 1;
}
