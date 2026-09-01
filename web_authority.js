(() => {
  'use strict';

  const PANEL_ID = 'authority-panel';
  const STATUS_ID = 'authority-status';
  const TRACE_ID = 'authority-trace';
  const TRACE_SLIDER_ID = 'authority-trace-slider';
  const TRACE_LABEL_ID = 'authority-trace-label';
  const DEBUG_BASE = '/api/debug/sessions';

  let debugSessionId = null;
  let debugRunTimer = null;
  let debugRunActive = false;
  let debugRequestBusy = false;
  let debugGeneration = 0;

  function esc(value) {
    return String(value)
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#039;');
  }

  function jsonStable(value) {
    if (Array.isArray(value)) return `[${value.map(jsonStable).join(',')}]`;
    if (value && typeof value === 'object') {
      return `{${Object.keys(value).sort().map(k => `${JSON.stringify(k)}:${jsonStable(value[k])}`).join(',')}}`;
    }
    return JSON.stringify(value);
  }

  function serverModeEnabled() {
    return typeof window !== 'undefined'
      && window.location
      && window.location.protocol.startsWith('http');
  }

  function setAuthorityStatus(html, tone = 'info') {
    if (typeof document === 'undefined') return;
    const el = document.getElementById(STATUS_ID);
    if (!el) return;
    const colors = {
      ok: '#7ee787',
      err: '#ff7b72',
      warn: '#d29922',
      info: '#8b949e'
    };
    el.style.color = colors[tone] || colors.info;
    el.innerHTML = html;
  }

  function normalizePythonOutboxes(state) {
    const result = {};
    const entries = state && state.grid && Array.isArray(state.grid.outboxes)
      ? state.grid.outboxes : [];
    for (const entry of entries) {
      result[`${entry.x},${entry.y}`] = Array.isArray(entry.queue) ? entry.queue : [];
    }
    return result;
  }

  function normalizeJsOutboxes() {
    if (!vm || !vm.grid || !vm.grid.outboxes) return {};
    const result = {};
    for (const [key, queue] of Object.entries(vm.grid.outboxes)) {
      result[key] = Array.isArray(queue) ? [...queue] : [];
    }
    return result;
  }

  function clientTerminalProjection() {
    if (!vm) return null;
    const winResult = typeof vm.checkWin === 'function' ? vm.checkWin() : [false, ''];
    const robots = Array.isArray(vm.robots) ? vm.robots.map(r => ({
      x: r.x,
      y: r.y,
      facing: r.facing,
      inventory: r.inventory,
      registers: {...r.registers},
      pc: r.pc,
      halted: !!r.halted
    })) : [];
    return {
      won: !!winResult[0],
      cycles: vm.cycles,
      size: Array.isArray(instructions) ? instructions.length : 0,
      outboxes: normalizeJsOutboxes(),
      robots,
      ram: vm.sharedRam ? {...vm.sharedRam} : {}
    };
  }

  function serverTerminalProjection(payload) {
    const state = payload.state || {};
    return {
      won: !!payload.won,
      cycles: payload.cycles,
      size: payload.size,
      outboxes: normalizePythonOutboxes(state),
      robots: Array.isArray(state.robots) ? state.robots.map(r => ({
        x: r.x,
        y: r.y,
        facing: r.facing,
        inventory: r.inventory,
        registers: {...r.registers},
        pc: r.pc,
        halted: !!r.halted
      })) : [],
      ram: state.ram || {}
    };
  }

  function isClientTerminal() {
    if (!vm) return false;
    const won = typeof vm.checkWin === 'function' && !!vm.checkWin()[0];
    return !!vm.halted || won;
  }

  function compareClientAndServer(payload) {
    if (!isClientTerminal()) {
      return {
        comparable: false,
        equal: false,
        message: 'Server result is authoritative. Run the browser VM to completion to enable JS ↔ Python differential comparison.'
      };
    }

    const client = clientTerminalProjection();
    const server = serverTerminalProjection(payload);
    const fields = ['won', 'cycles', 'size', 'outboxes', 'robots', 'ram'];
    const mismatches = [];
    for (const field of fields) {
      if (jsonStable(client[field]) !== jsonStable(server[field])) mismatches.push(field);
    }

    return {
      comparable: true,
      equal: mismatches.length === 0,
      mismatches,
      client,
      server,
      message: mismatches.length === 0
        ? 'JS and Python terminal states match.'
        : `Runtime drift detected in: ${mismatches.join(', ')}`
    };
  }

  function traceSnapshotHtml(snapshot, index, total) {
    if (!snapshot) return '<em>No trace snapshot.</em>';
    const robots = (snapshot.robots || []).map(r => {
      const regs = Object.entries(r.registers || {}).map(([k, v]) => `${k}=${v}`).join(' ');
      return `R${r.id}: PC=${r.pc} (${r.x},${r.y}) ${r.facing} INV=${r.inventory ?? '∅'} ${regs}${r.halted ? ' HALT' : ''}`;
    }).join('\n');
    const outboxes = normalizePythonOutboxes(snapshot);
    return `<div><strong>Snapshot ${index + 1}/${total}</strong> · cycle ${snapshot.cycles} · ${snapshot.halted ? 'halted' : 'running'}</div>` +
      `<pre style="white-space:pre-wrap;margin:6px 0 0;color:#c9d1d9">${esc(robots)}\nRAM ${esc(JSON.stringify(snapshot.ram || {}))}\nOUT ${esc(JSON.stringify(outboxes))}\nIPC ${esc(JSON.stringify(snapshot.messages || []))}</pre>`;
  }

  function renderTrace(trace) {
    if (typeof document === 'undefined') return;
    const holder = document.getElementById(TRACE_ID);
    const slider = document.getElementById(TRACE_SLIDER_ID);
    const label = document.getElementById(TRACE_LABEL_ID);
    if (!holder || !slider || !label) return;

    if (!Array.isArray(trace) || trace.length === 0) {
      slider.disabled = true;
      slider.max = '0';
      slider.value = '0';
      label.textContent = 'No trace';
      holder.innerHTML = '<em>No trace returned.</em>';
      return;
    }

    slider.disabled = false;
    slider.min = '0';
    slider.max = String(trace.length - 1);
    slider.value = String(trace.length - 1);

    const show = () => {
      const idx = Number(slider.value);
      label.textContent = `Trace cycle ${trace[idx].cycles}`;
      holder.innerHTML = traceSnapshotHtml(trace[idx], idx, trace.length);
    };
    slider.oninput = show;
    show();
  }

  async function parseJsonResponse(response) {
    let payload;
    try {
      payload = await response.json();
    } catch (_) {
      throw new Error(`Server returned HTTP ${response.status} without JSON.`);
    }
    if (!response.ok || payload.status === 'error') {
      const line = payload.line_num ? ` (line ${payload.line_num})` : '';
      const error = new Error(`${payload.error || payload.message || `HTTP ${response.status}`}${line}`);
      error.status = response.status;
      error.payload = payload;
      throw error;
    }
    return payload;
  }

  async function requestJson(path, options = {}) {
    return parseJsonResponse(await fetch(path, options));
  }

  async function deleteSession(sessionId, ignoreMissing = true) {
    if (!sessionId) return;
    try {
      await requestJson(`${DEBUG_BASE}/${encodeURIComponent(sessionId)}`, {method: 'DELETE'});
    } catch (error) {
      if (!(ignoreMissing && error.status === 404)) throw error;
    }
  }

  function coordEntriesToObject(entries, valueKey = 'value') {
    const result = {};
    for (const entry of Array.isArray(entries) ? entries : []) {
      result[`${entry.x},${entry.y}`] = Array.isArray(entry[valueKey])
        ? [...entry[valueKey]] : entry[valueKey];
    }
    return result;
  }

  function hydrateBrowserFromPython(payload, replaceVm = false) {
    if (!payload || !payload.state) throw new Error('Debugger response is missing VM state.');
    const state = payload.state;
    const levelDef = LEVELS[currentLevel];
    if (!levelDef) throw new Error('Current level definition is unavailable.');

    if (Array.isArray(payload.instructions)) instructions = payload.instructions.map(ins => ({...ins, args: [...(ins.args || [])]}));
    if (replaceVm || !vm || !Array.isArray(vm.robots) || vm.robots.length !== (state.robots || []).length) {
      vm = new VM(instructions, levelDef);
    }

    vm.instructions = instructions;
    vm.cycles = state.cycles;
    vm.halted = !!state.halted;
    vm.sharedRam = {...(state.ram || {})};
    vm.msgQueue = (state.messages || []).map(message => ({
      sender: message.sender_id,
      val: message.value,
    }));
    vm.faults = Array.isArray(state.faults) ? state.faults.map(fault => ({...fault})) : [];

    (state.robots || []).forEach((source, index) => {
      const robot = vm.robots[index];
      if (!robot) return;
      robot.x = source.x;
      robot.y = source.y;
      robot.facing = source.facing;
      robot.inventory = source.inventory;
      robot.registers = {...(source.registers || {})};
      robot.flags = {...(source.flags || {})};
      robot.stack = [...(source.stack || [])];
      robot.callStack = [...(source.call_stack || [])];
      robot.pc = source.pc;
      robot.halted = !!source.halted;
      robot.error = source.last_error ? source.last_error.message : null;
      robot.ram = vm.sharedRam;
    });

    if (state.grid) {
      vm.grid.items = coordEntriesToObject(state.grid.items, 'value');
      vm.grid.inboxes = coordEntriesToObject(state.grid.inboxes, 'queue');
      vm.grid.outboxes = coordEntriesToObject(state.grid.outboxes, 'queue');
      vm.grid.openDoors = new Set((state.grid.open_doors || []).map(entry => `${entry.x},${entry.y}`));
    }

    selectedRobot = Math.min(selectedRobot || 0, Math.max(0, vm.robots.length - 1));
    updateState();
    drawGrid(1.0);
    return vm;
  }

  function updateRunButtons(running) {
    if (typeof document === 'undefined') return;
    const runButton = document.getElementById('btn-run');
    const stopButton = document.getElementById('btn-stop');
    if (runButton) runButton.disabled = !!running;
    if (stopButton) stopButton.disabled = !running;
  }

  function finishAuthoritativeState(payload) {
    if (payload.won) {
      stopAuthoritativeRun();
      renderStars();
      setMsg(`🎉 ${payload.message} (Cycles: ${payload.cycles}, Inst: ${payload.size})`, 'msg-ok');
      setAuthorityStatus(`<strong>Python PASS</strong> · persistent session · cycle ${payload.cycles}`, 'ok');
      return true;
    }
    if (payload.terminal) {
      stopAuthoritativeRun();
      const faults = payload.state && payload.state.faults ? payload.state.faults : [];
      const detail = faults.length ? faults[faults.length - 1].message : payload.message;
      setMsg(`Execution stopped: ${detail || 'program halted'}`, faults.length ? 'msg-err' : 'msg-info');
      setAuthorityStatus(`<strong>Python session halted</strong> · cycle ${payload.cycles}`, faults.length ? 'err' : 'warn');
      return true;
    }
    return false;
  }

  async function compileAuthoritative() {
    stopAuthoritativeRun();
    const generation = ++debugGeneration;
    const previousSession = debugSessionId;
    debugSessionId = null;
    if (previousSession) deleteSession(previousSession, true).catch(() => {});

    const def = LEVELS[currentLevel];
    if (!def || !def.filename) {
      setMsg('Current level has no server filename.', 'msg-err');
      return;
    }

    const code = document.getElementById('code').value;
    const optimizeInput = document.getElementById('chk-opt');
    const optimize = !!(optimizeInput && optimizeInput.checked);
    setMsg('Compiling with authoritative Python assembler…', 'msg-info');
    setAuthorityStatus('Creating persistent Python debugger session…', 'info');

    try {
      const payload = await requestJson(DEBUG_BASE, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({level: def.filename, code, optimize}),
      });
      if (generation !== debugGeneration) {
        deleteSession(payload.session_id, true).catch(() => {});
        return;
      }
      debugSessionId = payload.session_id;
      vmHistory = [];
      selectedRobot = 0;
      const stars = document.getElementById('stars-display');
      if (stars) stars.innerHTML = '';
      hydrateBrowserFromPython(payload, true);
      setMsg(`Python compiled successfully (${payload.size} instructions${payload.optimized ? ' | Optimized' : ''}). Ready.`, 'msg-ok');
      setAuthorityStatus(`<strong>Authoritative debugger ready</strong> · session ${esc(payload.session_id.slice(0, 8))}… · cycle 0`, 'ok');
    } catch (error) {
      if (generation !== debugGeneration) return;
      vm = null;
      instructions = [];
      setMsg(`Assembly Error: ${error.message}`, 'msg-err');
      setAuthorityStatus(`<strong>Debugger session failed:</strong> ${esc(error.message)}`, 'err');
    }
  }

  async function ensureDebugSession() {
    if (debugSessionId) return true;
    await compileAuthoritative();
    return !!debugSessionId;
  }

  async function stepAuthoritatively() {
    if (debugRequestBusy || debugRunActive) return;
    if (!(await ensureDebugSession())) return;
    if (!vm || vm.halted) return;

    debugRequestBusy = true;
    const sessionId = debugSessionId;
    try {
      const payload = await requestJson(`${DEBUG_BASE}/${encodeURIComponent(sessionId)}/step`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({cycles: 1}),
      });
      if (sessionId !== debugSessionId) return;
      hydrateBrowserFromPython(payload, false);
      finishAuthoritativeState(payload);
      if (!payload.terminal) setAuthorityStatus(`<strong>Python Step</strong> · persistent session · cycle ${payload.cycles}`, 'info');
    } catch (error) {
      if (error.status === 404 && sessionId === debugSessionId) debugSessionId = null;
      setMsg(`Debugger step failed: ${error.message}`, 'msg-err');
      setAuthorityStatus(`<strong>Python Step failed:</strong> ${esc(error.message)}`, 'err');
    } finally {
      debugRequestBusy = false;
    }
  }

  function stopAuthoritativeRun() {
    debugRunActive = false;
    if (debugRunTimer) clearTimeout(debugRunTimer);
    debugRunTimer = null;
    updateRunButtons(false);
  }

  async function authoritativeRunTick() {
    if (!debugRunActive || debugRequestBusy || !debugSessionId || !vm) return;
    if (vm.halted) {
      stopAuthoritativeRun();
      return;
    }

    const robot = vm.robots[selectedRobot];
    const currentRobotLine = robot ? instructions[robot.pc]?.line_num : null;
    if (currentRobotLine && breakpoints.has(currentRobotLine) && vm.cycles > 0) {
      stopAuthoritativeRun();
      setMsg(`Breakpoint hit on line ${currentRobotLine}`, 'msg-err');
      setAuthorityStatus(`<strong>Breakpoint</strong> · Python session paused at cycle ${vm.cycles}`, 'warn');
      return;
    }

    debugRequestBusy = true;
    const sessionId = debugSessionId;
    try {
      const payload = await requestJson(`${DEBUG_BASE}/${encodeURIComponent(sessionId)}/step`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({cycles: 1}),
      });
      if (!debugRunActive || sessionId !== debugSessionId) return;
      hydrateBrowserFromPython(payload, false);
      if (finishAuthoritativeState(payload)) return;
      const speed = Math.max(1, parseInt(document.getElementById('speed').value, 10) || 1);
      const interval = Math.max(20, 500 / speed);
      debugRunTimer = setTimeout(authoritativeRunTick, interval);
    } catch (error) {
      stopAuthoritativeRun();
      if (error.status === 404 && sessionId === debugSessionId) debugSessionId = null;
      setMsg(`Debugger run failed: ${error.message}`, 'msg-err');
      setAuthorityStatus(`<strong>Python Run failed:</strong> ${esc(error.message)}`, 'err');
    } finally {
      debugRequestBusy = false;
    }
  }

  async function runAuthoritatively() {
    if (debugRunActive) return;
    if (!(await ensureDebugSession())) return;
    if (!vm || vm.halted) return;
    debugRunActive = true;
    updateRunButtons(true);
    setAuthorityStatus(`<strong>Python Run</strong> · persistent session · cycle ${vm.cycles}`, 'info');
    authoritativeRunTick();
  }

  async function callAuthoritativeRuntime(captureTrace) {
    const def = LEVELS[currentLevel];
    if (!def || !def.filename) throw new Error('Current level has no server filename.');
    const code = document.getElementById('code').value;
    const maxCyclesInput = document.getElementById('authority-max-cycles');
    const maxCycles = Number(maxCyclesInput ? maxCyclesInput.value : 1000);
    const optimizeInput = document.getElementById('chk-opt');
    const optimize = !!(optimizeInput && optimizeInput.checked);

    return requestJson('/api/run', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        level: def.filename,
        code,
        max_cycles: maxCycles,
        capture_trace: !!captureTrace,
        optimize
      })
    });
  }

  async function verifyAuthoritatively(captureTrace = false) {
    const verifyBtn = document.getElementById('btn-server-verify');
    const traceBtn = document.getElementById('btn-server-trace');
    if (verifyBtn) verifyBtn.disabled = true;
    if (traceBtn) traceBtn.disabled = true;
    setAuthorityStatus('Running Python assembler + VM…', 'info');

    try {
      const payload = await callAuthoritativeRuntime(captureTrace);
      const diff = compareClientAndServer(payload);
      const authority = payload.won ? 'PASS' : 'NOT SOLVED';
      const tone = payload.won ? 'ok' : 'warn';
      const faultCount = payload.execution && payload.execution.faults
        ? payload.execution.faults.length : 0;
      const compileMode = payload.optimized ? 'optimized' : 'unoptimized';

      let diffHtml;
      if (!diff.comparable) {
        diffHtml = `<div style="margin-top:4px;color:#8b949e">${esc(diff.message)}</div>`;
      } else if (diff.equal) {
        diffHtml = `<div style="margin-top:4px;color:#7ee787">✓ ${esc(diff.message)}</div>`;
      } else {
        diffHtml = `<div style="margin-top:4px;color:#ff7b72">⚠ ${esc(diff.message)}</div>`;
      }

      setAuthorityStatus(
        `<strong>Python ${authority}</strong> · ${payload.cycles} cycles · ${payload.size} instructions · ${compileMode} · ${faultCount} faults` +
        `<div style="margin-top:4px">${esc(payload.message || '')}</div>${diffHtml}`,
        tone
      );

      const trace = payload.execution && payload.execution.trace;
      if (captureTrace) renderTrace(trace || []);
    } catch (error) {
      setAuthorityStatus(`<strong>Server verification failed:</strong> ${esc(error.message)}`, 'err');
      if (captureTrace) renderTrace([]);
    } finally {
      if (verifyBtn) verifyBtn.disabled = false;
      if (traceBtn) traceBtn.disabled = false;
    }
  }

  function installPanel() {
    if (document.getElementById(PANEL_ID)) return;
    const toolbar = document.getElementById('toolbar');
    if (!toolbar) return;

    const verifyBtn = document.createElement('button');
    verifyBtn.id = 'btn-server-verify';
    verifyBtn.textContent = '✓ Server Verify';
    verifyBtn.title = 'Run the current program through the authoritative Python assembler + VM';
    verifyBtn.onclick = () => verifyAuthoritatively(false);
    toolbar.appendChild(verifyBtn);

    const traceBtn = document.createElement('button');
    traceBtn.id = 'btn-server-trace';
    traceBtn.textContent = '≋ Python Trace';
    traceBtn.title = 'Run on the Python VM and capture cycle-by-cycle debugger snapshots';
    traceBtn.onclick = () => verifyAuthoritatively(true);
    toolbar.appendChild(traceBtn);

    const panel = document.createElement('section');
    panel.id = PANEL_ID;
    panel.style.cssText = 'margin:10px 0;padding:10px 12px;border:1px solid #30363d;border-radius:6px;background:#0d1117;font:12px Consolas,monospace;';
    panel.innerHTML = `
      <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:8px">
        <strong style="color:#58a6ff">Authoritative Python Runtime</strong>
        <label style="color:#8b949e">Max cycles <input id="authority-max-cycles" type="number" min="0" max="2000" value="1000" style="width:74px;background:#161b22;color:#c9d1d9;border:1px solid #30363d;border-radius:4px;padding:2px 4px"></label>
        <span style="color:#6e7681">HTTP IDE Compile / Step / Run use one persistent Python VM session. Server Verify remains an independent replay check.</span>
      </div>
      <div id="${STATUS_ID}" style="color:#8b949e">Authoritative debugger controller installed.</div>
      <div style="display:flex;align-items:center;gap:8px;margin-top:10px">
        <input id="${TRACE_SLIDER_ID}" type="range" min="0" max="0" value="0" disabled style="flex:1">
        <span id="${TRACE_LABEL_ID}" style="color:#8b949e;min-width:120px">No trace</span>
      </div>
      <div id="${TRACE_ID}" style="margin-top:6px;max-height:190px;overflow:auto;color:#c9d1d9"></div>
    `;

    const grid = document.getElementById('grid-canvas');
    const anchor = grid ? grid.closest('section,div') : null;
    if (anchor && anchor.parentNode) anchor.parentNode.insertBefore(panel, anchor);
    else toolbar.insertAdjacentElement('afterend', panel);
  }

  function installAuthoritativeControls() {
    if (!serverModeEnabled()) return false;
    if (typeof compileAndReset !== 'function' || typeof stepOnce !== 'function'
        || typeof runAuto !== 'function' || typeof stopAuto !== 'function') {
      throw new Error('Authoritative debugger controller could not find legacy IDE controls.');
    }

    globalThis.compileAndReset = compileAuthoritative;
    globalThis.stepOnce = stepAuthoritatively;
    globalThis.runAuto = runAuthoritatively;
    globalThis.stopAuto = stopAuthoritativeRun;

    const backButton = document.getElementById('btn-back');
    if (backButton) {
      backButton.disabled = true;
      backButton.title = 'Step Back is disabled while the HTTP IDE uses the authoritative Python debugger session.';
    }
    return true;
  }

  globalThis.ROBOASM_AUTHORITY_INTERNALS = Object.freeze({
    coordEntriesToObject,
    serverTerminalProjection,
    jsonStable,
  });

  if (typeof document !== 'undefined') {
    installPanel();
    installAuthoritativeControls();
  }

  if (typeof window !== 'undefined') {
    window.roboasmAuthoritativeVerify = verifyAuthoritatively;
  }
})();
