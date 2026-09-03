'use strict';
const assert=require('assert');const fs=require('fs');const s=fs.readFileSync('./BUILD-OPERATOR.sh','utf8');
function c(n,f){try{f();console.log(`${n}: PASS`)}catch(e){console.log(`${n}: FAIL ${e.message}`);process.exitCode=1}}
c('private unique workdir',()=>{assert(s.includes('mktemp -d "/tmp/zeus-host-runner-build.${RUN_ID}.XXXXXX"'));assert(s.includes('umask 077'))});
c('iid absent before build',()=>{assert(s.includes('test ! -e "$IID" && test ! -L "$IID"'));assert(s.includes('--iidfile "$IID"'))});
c('build failure stops',()=>{assert(s.includes('if test "$BUILD_RC" -ne 0; then'));assert(s.includes('exit "$BUILD_RC"'))});
c('inspect exact iid only',()=>{assert(s.includes('docker image inspect "$IMAGE_ID"'));assert(s.includes('INSPECT_ID'));assert(s.includes('test "$INSPECT_ID" = "$IMAGE_ID"'));assert(!s.includes('docker image inspect "$TAG"'))});
c('no tag fallback',()=>{assert(s.includes("grep -Eq '^sha256:[0-9a-f]{64}$'"));assert(s.includes('IMAGE_ID='))});
c('context allowlist',()=>{assert(s.includes('for f in Dockerfile runner.js runner-schema.json operations.allowlist.json adapter.js fake-backend.js lease.js work-queue-bridge.js daemon.js healthcheck.js readiness.js;'))});
c('context copied bytes rebound',()=>{assert(s.includes('context_hash_mismatch'));assert(s.includes('context-manifest.sha256'));assert(s.includes('CONTEXT_MANIFEST_SHA'))});
c('evidence bound to run',()=>{assert(s.includes('RUN_ID='));assert(s.includes('IIDFILE='));assert(s.includes('BUILD_RESULT=FAIL'))});
c('no unbounded cleanup',()=>{assert(!s.includes('rm -rf'));assert(s.includes('RETAIN_WORK='))});
