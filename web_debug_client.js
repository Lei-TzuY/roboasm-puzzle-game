(() => {
  'use strict';

  class RoboASMDebugClient {
    constructor(fetchImpl = globalThis.fetch, basePath = '/api/debug/sessions') {
      if (typeof fetchImpl !== 'function') throw new Error('fetch implementation is required');
      this.fetchImpl = fetchImpl;
      this.basePath = String(basePath).replace(/\/$/, '');
      this.sessionId = null;
    }

    get active() {
      return typeof this.sessionId === 'string' && this.sessionId.length > 0;
    }

    async _request(path, options = {}) {
      const response = await this.fetchImpl(path, options);
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

    async create({level, code, optimize = false}) {
      if (this.active) await this.close({ignoreMissing: true});
      const payload = await this._request(this.basePath, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({level, code, optimize: !!optimize}),
      });
      if (!payload.session_id) throw new Error('Debugger session response is missing session_id.');
      this.sessionId = payload.session_id;
      return payload;
    }

    _sessionPath(suffix = '') {
      if (!this.active) throw new Error('No active authoritative debugger session.');
      return `${this.basePath}/${encodeURIComponent(this.sessionId)}${suffix}`;
    }

    async state() {
      return this._request(this._sessionPath());
    }

    async step(cycles = 1) {
      return this._request(this._sessionPath('/step'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({cycles}),
      });
    }

    async run({maxCycles = 1000, captureTrace = false} = {}) {
      return this._request(this._sessionPath('/run'), {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({max_cycles: maxCycles, capture_trace: !!captureTrace}),
      });
    }

    async close({ignoreMissing = false} = {}) {
      if (!this.active) return false;
      const path = this._sessionPath();
      try {
        await this._request(path, {method: 'DELETE'});
      } catch (error) {
        if (!(ignoreMissing && error.status === 404)) throw error;
      } finally {
        this.sessionId = null;
      }
      return true;
    }
  }

  globalThis.RoboASMDebugClient = RoboASMDebugClient;
  globalThis.ROBOASM_WEB_DEBUG_CLIENT = Object.freeze({version: 1});
})();
