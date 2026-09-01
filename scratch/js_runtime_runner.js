#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');
const nodeVm = require('vm');

const ROOT_DIR = path.resolve(__dirname, '..');
const WEB_UI_PATH = path.join(ROOT_DIR, 'web_ui.html');
const RUNTIME_START = 'function lex(src)';
const RUNTIME_END = '// State & History Stack for Breakpoints & Step Back';

function loadEmbeddedRuntime() {
  const html = fs.readFileSync(WEB_UI_PATH, 'utf8');
  const start = html.indexOf(RUNTIME_START);
  const end = html.indexOf(RUNTIME_END, start);
  if (start < 0 || end < 0 || end <= start) {
    throw new Error('Could not locate embedded Web IDE runtime in web_ui.html');
  }

  const runtimeSource = html.slice(start, end);
  const sandbox = {
    console,
    playAudioSynth: () => {},
  };
  sandbox.globalThis = sandbox;
  nodeVm.createContext(sandbox);
  nodeVm.runInContext(
    `${runtimeSource}\nglobalThis.__roboasmRuntime = { lex, assemble, Grid, Robot, VM };`,
    sandbox,
    {filename: 'web_ui.runtime.js'},
  );
  return sandbox.__roboasmRuntime;
}

function parseCoord(key) {
  const [x, y] = String(key).split(',').map(Number);
  return {x, y};
}

function coordEntries(mapping, valueKey) {
  return Object.entries(mapping || {})
    .map(([key, value]) => ({...parseCoord(key), [valueKey]: cloneJson(value)}))
    .sort((a, b) => a.x - b.x || a.y - b.y);
}

function cloneJson(value) {
  if (value === undefined) return null;
  return JSON.parse(JSON.stringify(value));
}

function sortObject(mapping) {
  const result = {};
  for (const key of Object.keys(mapping || {}).sort((a, b) => Number(a) - Number(b) || a.localeCompare(b))) {
    result[String(key)] = cloneJson(mapping[key]);
  }
  return result;
}

function snapshot(machine) {
  return {
    cycles: machine.cycles,
    halted: !!machine.halted,
    robots: machine.robots.map(robot => ({
      id: robot.id,
      x: robot.x,
      y: robot.y,
      facing: robot.facing,
      inventory: robot.inventory === undefined ? null : robot.inventory,
      registers: sortObject(robot.registers),
      flags: cloneJson(robot.flags || {}),
      stack: cloneJson(robot.stack || []),
      pc: robot.pc,
      call_stack: cloneJson(robot.callStack || []),
      halted: !!robot.halted,
    })),
    ram: sortObject(machine.sharedRam || {}),
    messages: (machine.msgQueue || []).map(message => ({
      sender_id: message.sender,
      value: cloneJson(message.val),
    })),
    grid: {
      width: machine.grid.width,
      height: machine.grid.height,
      items: coordEntries(machine.grid.items, 'value'),
      inboxes: coordEntries(machine.grid.inboxes, 'queue'),
      outboxes: coordEntries(machine.grid.outboxes, 'queue'),
      open_doors: Array.from(machine.grid.openDoors || [])
        .map(parseCoord)
        .sort((a, b) => a.x - b.x || a.y - b.y),
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
      limit_reached: !machine.halted && !winResult[0] && machine.cycles >= maxCycles,
      state: snapshot(machine),
      trace,
    };
  } catch (error) {
    return {
      name: testCase.name,
      status: 'error',
      error: error && error.stack ? error.stack : String(error),
    };
  }
}

function main() {
  const raw = fs.readFileSync(0, 'utf8');
  const request = JSON.parse(raw || '{}');
  if (!Array.isArray(request.cases)) {
    throw new Error("Input JSON must contain a 'cases' array");
  }

  const runtime = loadEmbeddedRuntime();
  const results = request.cases.map(testCase => runCase(runtime, testCase));
  process.stdout.write(JSON.stringify({results}));
}

try {
  main();
} catch (error) {
  process.stderr.write(`${error && error.stack ? error.stack : error}\n`);
  process.exitCode = 1;
}
