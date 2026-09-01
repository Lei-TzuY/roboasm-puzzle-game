'use strict';

const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vmModule = require('vm');

function response(status, payload) {
  return {
    ok: status >= 200 && status < 300,
    status,
    async json() { return payload; },
  };
}

function snapshot(cycles, {won = false, halted = false} = {}) {
  return {
    status: 'success',
    session_id: 'session-123',
    won,
    message: won ? 'Level Complete!' : 'Waiting',
    terminal: won || halted,
    cycles,
    size: 2,
    optimized: false,
    instructions: [
      {opcode: 'MOV', args: [cycles + 1, 'R0'], line_num: 1},
      {opcode: 'HLT', args: [], line_num: 2},
    ],
    state: {
      cycles,
      halted,
      ram: {0: cycles},
      messages: [{sender_id: 1, value: 9}],
      faults: [],
      robots: [{
        id: 0,
        x: cycles,
        y: 0,
        facing: 'E',
        inventory: null,
        registers: {R0: cycles, R1: 0, R2: 0, R3: 0},
        flags: {ZERO: false, NEGATIVE: false},
        stack: [cycles],
        call_stack: [],
        pc: cycles === 0 ? 0 : 1,
        halted,
        last_error: null,
      }],
      grid: {
        items: [{x: 1, y: 1, value: cycles}],
        inboxes: [{x: 0, y: 0, queue: [1, 2]}],
        outboxes: [{x: 2, y: 0, queue: won ? [42] : []}],
        open_doors: cycles ? [{x: 1, y: 0}] : [],
      },
    },
  };
}

const controls = new Map();
function control(id, extra = {}) {
  const value = {id, disabled: false, style: {}, ...extra};
  controls.set(id, value);
  return value;
}

const toolbar = control('toolbar', {
  appendChild() {},
  insertAdjacentElement() {},
});
control('grid-canvas', {closest() { return null; }});
control('btn-back');
control('btn-run');
control('btn-stop', {disabled: true});
control('code', {value: 'MOV 1 R0\nHLT\n'});
control('chk-opt', {checked: false});
control('stars-display', {innerHTML: ''});
control('speed', {value: '100'});

const document = {
  readyState: 'complete',
  getElementById(id) { return controls.get(id) || null; },
  createElement(tag) {
    return {
      tag,
      id: '',
      textContent: '',
      title: '',
      disabled: false,
      style: {},
      innerHTML: '',
      onclick: null,
    };
  },
};

class FakeVM {
  constructor(instructions, levelDef) {
    this.instructions = instructions;
    this.levelDef = levelDef;
    this.cycles = 0;
    this.halted = false;
    this.sharedRam = {};
    this.msgQueue = [];
    this.robots = [{
      x: 0, y: 0, facing: 'N', inventory: null,
      registers: {R0: 0, R1: 0, R2: 0, R3: 0},
      flags: {ZERO: false, NEGATIVE: false},
      stack: [], callStack: [], pc: 0, halted: false, ram: {},
    }];
    this.grid = {
      items: {}, inboxes: {}, outboxes: {}, openDoors: new Set(),
    };
  }
}

const requests = [];
let stepCount = 0;
async function fetchMock(url, options = {}) {
  requests.push({url, options});
  if (url === '/api/debug/sessions' && options.method === 'POST') {
    return response(201, snapshot(0));
  }
  if (url === '/api/debug/sessions/session-123/step' && options.method === 'POST') {
    stepCount += 1;
    return response(200, snapshot(stepCount, {won: stepCount >= 2, halted: stepCount >= 2}));
  }
  if (url === '/api/debug/sessions/session-123' && options.method === 'DELETE') {
    return response(200, {status: 'success', deleted: true});
  }
  throw new Error(`Unexpected request ${options.method || 'GET'} ${url}`);
}

const messages = [];
const sandbox = {
  console,
  document,
  window: {location: {protocol: 'http:'}},
  fetch: fetchMock,
  setTimeout,
  clearTimeout,
  Set,
  Map,
  JSON,
  Math,
  Number,
  String,
  Object,
  Array,
  Promise,
  VM: FakeVM,
  LEVELS: [{filename: 'level1.json', robots: [{x: 0, y: 0, facing: 'N'}]}],
  currentLevel: 0,
  instructions: [],
  vm: null,
  selectedRobot: 0,
  vmHistory: [],
  breakpoints: new Set(),
  updateState() {},
  drawGrid() {},
  renderStars() { sandbox.renderedStars = true; },
  setMsg(text, cls) { messages.push({text, cls}); },
  compileAndReset() { throw new Error('legacy compile should be replaced'); },
  stepOnce() { throw new Error('legacy step should be replaced'); },
  runAuto() { throw new Error('legacy run should be replaced'); },
  stopAuto() { throw new Error('legacy stop should be replaced'); },
};
sandbox.globalThis = sandbox;
vmModule.createContext(sandbox);

const source = fs.readFileSync(path.join(__dirname, '..', 'web_authority.js'), 'utf8');
vmModule.runInContext(source, sandbox, {filename: 'web_authority.js'});

(async () => {
  assert.strictEqual(controls.get('btn-back').disabled, true, 'server mode must disable local Step Back');

  await sandbox.compileAndReset();
  assert.strictEqual(requests[0].url, '/api/debug/sessions');
  assert.strictEqual(sandbox.vm.cycles, 0);
  assert.strictEqual(sandbox.vm.sharedRam['0'], 0);
  assert.deepStrictEqual(Array.from(sandbox.vm.grid.inboxes['0,0']), [1, 2]);

  await sandbox.stepOnce();
  assert.strictEqual(sandbox.vm.cycles, 1);
  assert.strictEqual(sandbox.vm.robots[0].registers.R0, 1);
  assert.strictEqual(sandbox.vm.robots[0].x, 1);
  assert.strictEqual(sandbox.vm.sharedRam['0'], 1);
  assert.ok(sandbox.vm.grid.openDoors.has('1,0'));
  assert.deepStrictEqual(
    JSON.parse(JSON.stringify(sandbox.vm.msgQueue)),
    [{sender: 1, val: 9}],
    'Python IPC messages must hydrate to the legacy inspector shape'
  );

  sandbox.runAuto();
  await new Promise(resolve => setTimeout(resolve, 80));
  assert.strictEqual(sandbox.vm.cycles, 2, 'Run must continue the same persistent session');
  assert.strictEqual(sandbox.vm.halted, true);
  assert.strictEqual(sandbox.renderedStars, true);
  assert.strictEqual(controls.get('btn-run').disabled, false);
  assert.strictEqual(controls.get('btn-stop').disabled, true);
  assert.ok(messages.some(entry => entry.text.includes('Level Complete')));

  const createCount = requests.filter(entry => entry.url === '/api/debug/sessions').length;
  assert.strictEqual(createCount, 1, 'Step and Run must not replay source from cycle zero');
  assert.strictEqual(stepCount, 2, 'one manual Step plus one Run tick should reach terminal state');

  console.log('Web authoritative debugger controller integration: PASS');
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
