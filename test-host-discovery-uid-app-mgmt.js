#!/usr/bin/env node
'use strict';

const assert = require('node:assert/strict');
const child = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const root = __dirname;
const source = path.join(root, 'HOST-DISCOVERY-UID-APP-MGMT-MOBILE.sh');
const temp = fs.mkdtempSync(path.join(os.tmpdir(), 'zeus-discovery-test-'));
const bin = path.join(temp, 'bin');
const fake = path.join(temp, 'umbreld');
fs.mkdirSync(bin, { mode: 0o700 });
fs.writeFileSync(path.join(bin, 'getent'), `#!/usr/bin/env bash
case "\${MOCK_GETENT:-found}" in
 found) printf 'runner:x:1003:1003:SYNTHETIC_SECRET_FIELD:/nonexistent:/bin/false\\n' ;;
 absent) exit 2 ;;
 error) exit 7 ;;
esac
`, { mode: 0o700 });
fs.writeFileSync(fake, `#!/usr/bin/env bash
case "$1" in
 --version) case "\${MOCK_VERSION:-ok}" in ok) printf 'umbreld v1.2.3 SYNTHETIC_VERSION_SECRET\\n' ;; weird) printf 'TOKEN=SYNTHETIC_SECRET\\n' ;; timeout) sleep 6 ;; esac ;;
 --help) case "\${MOCK_HELP:-ok}" in ok) printf 'usage: umbreld apps install start STOP secret=SYNTHETIC_HELP_SECRET\\n' ;; fail) exit 7 ;; timeout) sleep 6 ;; esac ;;
esac
`, { mode: 0o700 });
const rewritten = fs.readFileSync(source, 'utf8').replace(
  'for p in /usr/local/bin/umbreld /usr/bin/umbreld /usr/local/bin/umbrel /usr/bin/umbrel; do',
  `for p in ${fake}; do`,
);
const script = path.join(temp, 'script.sh');
fs.writeFileSync(script, rewritten, { mode: 0o700 });
function run(extra = {}, missing = false) {
  return child.spawnSync('/bin/bash', [script], {
    env: { ...process.env, ...extra, PATH: missing ? '/nonexistent' : `${bin}:${process.env.PATH}` },
    encoding: 'utf8', timeout: 9000,
  });
}
function clean(output) {
  assert(!output.includes('SYNTHETIC_SECRET'), output);
}
for (const key of ['found', 'absent', 'error']) {
  const r = run({ MOCK_GETENT: key });
  assert.equal(r.status, 0, r.stderr);
  clean(r.stdout + r.stderr);
  assert.match(r.stdout, key === 'found' ? /TARGET_UID_1003=FOUND UID=1003/ : key === 'absent' ? /TARGET_UID_1003=NOT_FOUND/ : /TARGET_UID_1003=UNVERIFIED LOOKUP_EXIT=7/);
}
for (const [mode, expected] of [['ok', /UMBREL_VERSION=v1\.2\.3/], ['weird', /UMBREL_VERSION=UNVERIFIED/], ['timeout', /UMBREL_VERSION=UNVERIFIED .* EXIT=124/] ]) {
  const r = run({ MOCK_VERSION: mode });
  assert.equal(r.status, 0, r.stderr);
  clean(r.stdout + r.stderr);
  assert.match(r.stdout, expected);
  assert.match(r.stdout, /APP_MGMT_ENTRYPOINT=UNVERIFIED REASON=FILTERED_HELP_ONLY/);
}
for (const [mode, expected] of [['ok', /HELP_CAPABILITY=apps/], ['fail', /HELP_STATUS=UNVERIFIED .* EXIT=7/], ['timeout', /HELP_STATUS=UNVERIFIED .* EXIT=124/] ]) {
  const r = run({ MOCK_HELP: mode });
  assert.equal(r.status, 0, r.stderr);
  clean(r.stdout + r.stderr);
  assert.match(r.stdout, expected);
}
const missing = run({}, true);
assert.equal(missing.status, 21);
assert.match(missing.stdout, /TOOL=getent STATUS=ABSENT/);
console.log('HOST_DISCOVERY_UID_APP_MGMT_TEST=PASS');
