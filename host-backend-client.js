'use strict';
const net = require('net');

const DEFAULT_SOCKET = process.env.ZEUS_HOST_ADAPTER_SOCKET || '/host-adapter/adapter.sock';
const MAX_LINE = 65536;
const TIMEOUTS = {
  candidate_preflight: 30000,
  build_rescue: 240000,
  inspect_image: 30000,
  run_rescue_test: 180000,
  cleanup_own_temp: 30000,
};

class HostBackendClient {
  constructor(socketPath = DEFAULT_SOCKET) { this.socketPath = socketPath; }

  invoke(request) {
    const timeout = TIMEOUTS[request.operation] || 30000;
    return new Promise((resolve) => {
      let done = false;
      let buf = '';
      const finish = (r) => { if (!done) { done = true; resolve(r); } };
      const c = net.createConnection(this.socketPath);
      const timer = setTimeout(() => {
        c.destroy();
        finish({status:'UNVERIFIED', exit_code:124, reason:'HOST_ADAPTER_TIMEOUT'});
      }, timeout);
      c.setEncoding('utf8');
      c.on('connect', () => c.write(JSON.stringify(request) + '\n'));
      c.on('data', (chunk) => {
        buf += chunk;
        if (buf.length > MAX_LINE) {
          clearTimeout(timer); c.destroy();
          finish({status:'UNVERIFIED', exit_code:65, reason:'HOST_ADAPTER_RESPONSE_TOO_LARGE'});
          return;
        }
        const i = buf.indexOf('\n');
        if (i >= 0) {
          clearTimeout(timer); c.end();
          try {
            const r = JSON.parse(buf.slice(0, i));
            if (!r || typeof r !== 'object' || !['PASS','FAIL','UNVERIFIED','RECOVERY_REQUIRED'].includes(r.status) || !Number.isInteger(r.exit_code)) {
              return finish({status:'UNVERIFIED', exit_code:65, reason:'HOST_ADAPTER_RESPONSE_INVALID'});
            }
            finish(r);
          } catch (_) {
            finish({status:'UNVERIFIED', exit_code:65, reason:'HOST_ADAPTER_RESPONSE_INVALID'});
          }
        }
      });
      c.on('error', () => {
        clearTimeout(timer);
        finish({status:'UNVERIFIED', exit_code:111, reason:'HOST_ADAPTER_CONNECT_FAILED'});
      });
    });
  }

  candidatePreflight(request) { return this.invoke({...request, operation:'candidate_preflight'}); }
  buildRescue(request) { return this.invoke({...request, operation:'build_rescue'}); }
  inspectImage(request) { return this.invoke({...request, operation:'inspect_image'}); }
  runRescueTest(request) { return this.invoke({...request, operation:'run_rescue_test'}); }
  cleanupOwnTemp(request) { return this.invoke({...request, operation:'cleanup_own_temp'}); }
}

module.exports = {HostBackendClient, TIMEOUTS, DEFAULT_SOCKET};
