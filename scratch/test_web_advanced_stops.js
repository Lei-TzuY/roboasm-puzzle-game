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

const controls = new Map();
function control(id, extra = {}) {
  const value = {id, value: '', checked: false, ...extra};
  controls.set(id, value);
  return value;
}

control('authority-cond-enabled', {checked: true});
control('authority-cond-line', {value: '12'});
control('authority-cond-expr', {value: 'R0 == 3 and RAM[0] != 7'});
control('authority-reg-watch-enabled', {checked: true});
control('authority-reg-watch-name', {value: 'R1'});
control('authority-ram-watch-enabled', {checked: true});
control('authority-ram-watch-address', {value: '4'});

const panelChildren = [];
control('authority-panel', {
  appendChild(child) { panelChildren.push(child); if (child.id) controls.set(child.id, child); },
});

const document = {
  getElementById(id) { return controls.get(id) || null; },
  createElement(tag) {
    return {tag, id: '', style: {}, innerHTML: ''};
  },
};

class FakeRobot {
  constructor() {
    this.pc = 0;
    this.halted = false;
    this.registers = {R0: 0, R1: 0, R2: 0, R3: 0};
    this.ram = {};
  }
  step() { this.pc += 1; }
  getVal(value) { return typeof value === 'number' ? value : (this.registers[value] || 0); }
  setVal(name, value) { this.registers[name] = value; }
}

class FakeVM {
  constructor() {
    this.robots = [new FakeRobot()];
    this.sharedRam = {};
  }
}

const requests = [];
let mode = 'watchpoint';
async function fetchMock(url, options = {}) {
  const body = JSON.parse(options.body || '{}');
  requests.push({url, options, body});
  if (mode === 'watchpoint') {
    return response(200, {
      status: 'success',
      cycles: 3,
      execution: {
        stopped_by_breakpoint: false,
        breakpoint: null,
        stopped_by_watchpoint: true,
        watchpoint: {
          kind: 'ram', address: 4,
          old_exists: true, old_value: 1,
          new_exists: true, new_value: 9,
          cycle: 3,
        },
      },
    });
  }
  return response(200, {
    status: 'success',
    cycles: 2,
    execution: {
      stopped_by_breakpoint: true,
      breakpoint: {
        kind: 'conditional', robot_id: 0, pc: 2,
        line_num: 12, condition: 'R0 == 3 and RAM[0] != 7', cycle: 2,
      },
      stopped_by_watchpoint: false,
      watchpoint: null,
    },
  });
}

const messages = [];
let stopCount = 0;
const sandbox = {
  console,
  document,
  window: {location: {protocol: 'http:'}},
  fetch: fetchMock,
  setTimeout(fn) { fn(); return 1; },
  clearTimeout() {},
  Robot: FakeRobot,
  VM: FakeVM,
  BigInt,
  Number,
  String,
  Object,
  Array,
  JSON,
  Math,
  Promise,
  setMsg(text, cls) { messages.push({text, cls}); },
  stopAuto() { stopCount += 1; },
};
sandbox.globalThis = sandbox;
vmModule.createContext(sandbox);

const source = fs.readFileSync(path.join(__dirname, '..', 'web_runtime_compat.js'), 'utf8');
vmModule.runInContext(source, sandbox, {filename: 'web_runtime_compat.js'});

(async () => {
  assert.strictEqual(sandbox.ROBOASM_WEB_RUNTIME_COMPAT.version, 4);
  assert.ok(sandbox.ROBOASM_WEB_RUNTIME_COMPAT.fixes.includes('advanced-debug-stops'));
  assert.strictEqual(panelChildren.length, 1, 'advanced stop editor should attach to authority panel');

  const spec = sandbox.ROBOASM_ADVANCED_STOPS.buildStopSpec([5], 0);
  assert.deepStrictEqual(JSON.parse(JSON.stringify(spec)), {
    lines: [5],
    conditional_breakpoints: [{
      line_num: 12,
      condition: 'R0 == 3 and RAM[0] != 7',
      robot_id: 0,
    }],
    watchpoints: [
      {kind: 'register', robot_id: 0, name: 'R1'},
      {kind: 'ram', address: 4},
    ],
  });

  const watchResponse = await sandbox.fetch('/api/debug/sessions/session-123/run', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      max_cycles: 16,
      breakpoint_lines: [5],
      breakpoint_robot_id: 0,
    }),
  });
  const watchPayload = await watchResponse.json();
  assert.strictEqual(watchPayload.execution.stopped_by_watchpoint, true);
  assert.strictEqual(stopCount, 1, 'watchpoint response should pause authoritative Run');
  assert.ok(messages.some(entry => entry.text.includes('RAM[4]') && entry.text.includes('1') && entry.text.includes('9')));
  assert.deepStrictEqual(
    JSON.parse(JSON.stringify(requests[0].body.breakpoint_lines)),
    JSON.parse(JSON.stringify(spec))
  );

  mode = 'conditional';
  const conditionalResponse = await sandbox.fetch('/api/debug/sessions/session-123/run', {
    method: 'POST',
    body: JSON.stringify({
      max_cycles: 16,
      breakpoint_lines: [],
      breakpoint_robot_id: 0,
    }),
  });
  const conditionalPayload = await conditionalResponse.json();
  assert.strictEqual(conditionalPayload.execution.breakpoint.kind, 'conditional');
  assert.strictEqual(sandbox.ROBOASM_ADVANCED_LAST_HIT.condition, 'R0 == 3 and RAM[0] != 7');

  // web_authority emits a generic line-breakpoint message; the compatibility
  // layer decorates it with the authoritative condition text.
  sandbox.setMsg('Breakpoint hit on line 12', 'msg-err');
  assert.ok(messages[messages.length - 1].text.includes('Conditional breakpoint line 12'));
  assert.ok(messages[messages.length - 1].text.includes('R0 == 3'));

  controls.get('authority-cond-enabled').checked = false;
  controls.get('authority-reg-watch-enabled').checked = false;
  controls.get('authority-ram-watch-enabled').checked = false;
  assert.deepStrictEqual(
    Array.from(sandbox.ROBOASM_ADVANCED_STOPS.buildStopSpec([3, 7], 0)),
    [3, 7],
    'no advanced controls should preserve legacy breakpoint array transport'
  );

  console.log('Web advanced debugger stops integration: PASS');
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
