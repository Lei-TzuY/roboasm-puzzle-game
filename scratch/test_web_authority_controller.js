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

function snapshot(cycles, {won = false, halted = false, historyDepth = cycles, execution = null} = {}) {
  const payload = {
    status: 'success',
    session_id: 'session-123',
    won,
    message: won ? 'Level Complete!' : 'Waiting',
    terminal: won || halted,
    cycles,
    size: 2,
    optimized: false,
    history_depth: historyDepth,
    history_limit: 256,
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
  if (execution) payload.execution = execution;
  return payload;
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
control('speed', {value: '10'});

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
let serverCycle = 0;
const serverHistory = [];
async function fetchMock(url, options = {}) {
  requests.push({url, options});
  if (url === '/api/debug/sessions' && options.method === 'POST') {
    serverCycle = 0;
    serverHistory.length = 0;
    return response(201, snapshot(0, {historyDepth: 0}));
  }
  if (url === '/api/debug/sessions/session-123/step' && options.method === 'POST') {
    const body = JSON.parse(options.body || '{}');
    if (body.cycles === 1) {
      serverHistory.push(serverCycle);
      serverCycle += 1;
      return response(200, snapshot(serverCycle, {
        won: serverCycle >= 2,
        halted: serverCycle >= 2,
        historyDepth: serverHistory.length,
        execution: {
          cycles_executed: 1,
          total_cycles: serverCycle,
          stopped_by_breakpoint: false,
          breakpoint: null,
        },
      }));
    }
    if (body.cycles === -1) {
      const target = serverHistory.length ? serverHistory.pop() : serverCycle;
      const rewound = target === serverCycle ? 0 : 1;
      serverCycle = target;
      return response(200, {
        ...snapshot(serverCycle, {historyDepth: serverHistory.length}),
        rewind: {
          requested_cycles: 1,
          cycles_rewound: rewound,
          history_depth: serverHistory.length,
          history_limit: 256,
          at_history_start: serverHistory.length === 0,
        },
      });
    }
  }
  if (url === '/api/debug/sessions/session-123/run' && options.method === 'POST') {
    const body = JSON.parse(options.body || '{}');
    assert.strictEqual(body.max_cycles, 16, 'speed 10 should request a conservative 16-cycle chunk');
    assert.deepStrictEqual(body.breakpoint_lines, [], 'empty breakpoint set must be forwarded explicitly');
    assert.strictEqual(body.breakpoint_robot_id, 0);

    const start = serverCycle;
    while (serverCycle < 2 && serverCycle - start < body.max_cycles) {
      serverHistory.push(serverCycle);
      serverCycle += 1;
    }
    const won = serverCycle >= 2;
    return response(200, snapshot(serverCycle, {
      won,
      halted: won,
      historyDepth: serverHistory.length,
      execution: {
        cycles_executed: serverCycle - start,
        total_cycles: serverCycle,
        stopped_by_condition: won,
        stopped_by_breakpoint: false,
        breakpoint: null,
        limit_reached: !won && serverCycle - start >= body.max_cycles,
        faults: [],
      },
    }));
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
  renderStars() {
    sandbox.renderedStars = true;
    controls.get('stars-display').innerHTML = '***';
  },
  setMsg(text, cls) { messages.push({text, cls}); },
  compileAndReset() { throw new Error('legacy compile should be replaced'); },
  stepOnce() { throw new Error('legacy step should be replaced'); },
  stepBack() { throw new Error('legacy Step Back should be replaced'); },
  runAuto() { throw new Error('legacy run should be replaced'); },
  stopAuto() { throw new Error('legacy stop should be replaced'); },
};
sandbox.globalThis = sandbox;
vmModule.createContext(sandbox);

const source = fs.readFileSync(path.join(__dirname, '..', 'web_authority.js'), 'utf8');
vmModule.runInContext(source, sandbox, {filename: 'web_authority.js'});

(async () => {
  assert.strictEqual(controls.get('btn-back').disabled, true, 'cycle zero has no reverse checkpoint');
  assert.strictEqual(
    sandbox.ROBOASM_AUTHORITY_INTERNALS.debugRunChunkSize(),
    16,
    'controller should expose deterministic speed-to-chunk sizing'
  );

  await sandbox.compileAndReset();
  assert.strictEqual(requests[0].url, '/api/debug/sessions');
  assert.strictEqual(sandbox.vm.cycles, 0);
  assert.strictEqual(sandbox.vm.sharedRam['0'], 0);
  assert.strictEqual(controls.get('btn-back').disabled, true);
  assert.deepStrictEqual(Array.from(sandbox.vm.grid.inboxes['0,0']), [1, 2]);

  await sandbox.stepOnce();
  assert.strictEqual(sandbox.vm.cycles, 1);
  assert.strictEqual(sandbox.vm.robots[0].registers.R0, 1);
  assert.strictEqual(sandbox.vm.robots[0].x, 1);
  assert.strictEqual(sandbox.vm.sharedRam['0'], 1);
  assert.ok(sandbox.vm.grid.openDoors.has('1,0'));
  assert.strictEqual(controls.get('btn-back').disabled, false, 'forward Step must create a server checkpoint');
  assert.deepStrictEqual(
    JSON.parse(JSON.stringify(sandbox.vm.msgQueue)),
    [{sender: 1, val: 9}],
    'Python IPC messages must hydrate to the legacy inspector shape'
  );

  sandbox.runAuto();
  await new Promise(resolve => setTimeout(resolve, 80));
  assert.strictEqual(sandbox.vm.cycles, 2, 'Run chunk must continue the same persistent session');
  assert.strictEqual(sandbox.vm.halted, true);
  assert.strictEqual(sandbox.renderedStars, true);
  assert.strictEqual(controls.get('btn-run').disabled, false);
  assert.strictEqual(controls.get('btn-stop').disabled, true);
  assert.strictEqual(controls.get('btn-back').disabled, false, 'terminal state must remain rewindable');
  assert.ok(messages.some(entry => entry.text.includes('Level Complete')));

  await sandbox.stepBack();
  assert.strictEqual(sandbox.vm.cycles, 1, 'Step Back must rewind the same Python session');
  assert.strictEqual(sandbox.vm.halted, false, 'rewinding terminal state must make it runnable again');
  assert.strictEqual(sandbox.vm.robots[0].registers.R0, 1);
  assert.strictEqual(controls.get('stars-display').innerHTML, '', 'rewinding a win clears terminal stars');
  assert.strictEqual(controls.get('btn-back').disabled, false, 'cycle one still retains cycle-zero checkpoint');

  sandbox.runAuto();
  await new Promise(resolve => setTimeout(resolve, 80));
  assert.strictEqual(sandbox.vm.cycles, 2, 'Run after rewind must branch forward from restored state');
  assert.strictEqual(sandbox.vm.halted, true);

  const createCount = requests.filter(entry => entry.url === '/api/debug/sessions').length;
  assert.strictEqual(createCount, 1, 'Step, batched Run, and Step Back must stay on one authoritative session');
  const stepBodies = requests
    .filter(entry => entry.url.endsWith('/step'))
    .map(entry => JSON.parse(entry.options.body).cycles);
  assert.deepStrictEqual(stepBodies, [1, -1], 'manual stepping and rewind stay signed /step operations');
  const runBodies = requests
    .filter(entry => entry.url.endsWith('/run'))
    .map(entry => JSON.parse(entry.options.body));
  assert.strictEqual(runBodies.length, 2, 'each Run phase should need one server chunk for this program');
  assert.ok(runBodies.every(body => body.max_cycles === 16));

  console.log('Web authoritative debugger controller integration: PASS');
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
