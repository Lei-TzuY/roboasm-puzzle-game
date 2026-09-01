(() => {
  'use strict';

  const PANEL_ID = 'authority-panel';
  const STATUS_ID = 'authority-status';
  const TRACE_ID = 'authority-trace';
  const TRACE_SLIDER_ID = 'authority-trace-slider';
  const TRACE_LABEL_ID = 'authority-trace-label';

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

  function setAuthorityStatus(html, tone = 'info') {
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
      label.textContent = `Trace cycle ${idx}/${trace.length - 1}`;
      holder.innerHTML = traceSnapshotHtml(trace[idx], idx, trace.length);
    };
    slider.oninput = show;
    show();
  }

  async function callAuthoritativeRuntime(captureTrace) {
    const def = LEVELS[currentLevel];
    if (!def || !def.filename) throw new Error('Current level has no server filename.');
    const code = document.getElementById('code').value;
    const maxCyclesInput = document.getElementById('authority-max-cycles');
    const maxCycles = Number(maxCyclesInput ? maxCyclesInput.value : 1000);

    const response = await fetch('/api/run', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        level: def.filename,
        code,
        max_cycles: maxCycles,
        capture_trace: !!captureTrace
      })
    });

    let payload;
    try {
      payload = await response.json();
    } catch (_) {
      throw new Error(`Server returned HTTP ${response.status} without JSON.`);
    }
    if (!response.ok || payload.status !== 'success') {
      const line = payload.line_num ? ` (line ${payload.line_num})` : '';
      throw new Error(`${payload.error || payload.message || `HTTP ${response.status}`}${line}`);
    }
    return payload;
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

      let diffHtml;
      if (!diff.comparable) {
        diffHtml = `<div style="margin-top:4px;color:#8b949e">${esc(diff.message)}</div>`;
      } else if (diff.equal) {
        diffHtml = `<div style="margin-top:4px;color:#7ee787">✓ ${esc(diff.message)}</div>`;
      } else {
        diffHtml = `<div style="margin-top:4px;color:#ff7b72">⚠ ${esc(diff.message)}</div>`;
      }

      setAuthorityStatus(
        `<strong>Python ${authority}</strong> · ${payload.cycles} cycles · ${payload.size} instructions · ${faultCount} faults` +
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
        <span style="color:#6e7681">Trace is capped at 2000 cycles.</span>
      </div>
      <div id="${STATUS_ID}" style="color:#8b949e">Use Server Verify to validate against the Python runtime.</div>
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

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', installPanel, {once: true});
  } else {
    installPanel();
  }

  window.roboasmAuthoritativeVerify = verifyAuthoritatively;
})();
