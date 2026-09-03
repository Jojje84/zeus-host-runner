'use strict';
const assert=require('assert');const fs=require('fs');const os=require('os');const {SESSION,MAX_RUNS,validate,claim,heartbeat,recover,loadState,saveState}=require('./work-queue-bridge');
const base={job_id:'q1',session:SESSION,change_id:'V31-ISO-20260902-002',idempotency_key:'q'.repeat(16),expires_at:new Date(60000).toISOString(),requested_by:'zeus-production',work_kind:'continue'};
const state=()=>({runs:0,seen:[],gate:false,recovery_required:false,quota:'verified',tool_policy:'approved',lease:null});
function t(n,f){try{f();console.log(`${n}: PASS`)}catch(e){console.log(`${n}: FAIL ${e.message}`);process.exitCode=1}}
t('named session',()=>assert.equal(validate(base,0).status,'PASS'));
t('duplicate',()=>{const s=state();claim(base,s,0);s.lease=null;assert.equal(claim({...base,job_id:'q2'},s,0).reason,'DUPLICATE')});
t('expiry',()=>assert.equal(validate({...base,expires_at:new Date(1).toISOString()},1000).reason,'EXPIRED'));
t('jorge gate',()=>assert.equal(claim(base,{...state(),gate:true},0).reason,'JORGE_DECISION_REQUIRED'));
t('quota ambiguity',()=>assert.equal(claim(base,{...state(),quota:'unknown'},0).reason,'QUOTA_OR_TOOL_POLICY_UNVERIFIED'));
t('tool policy ambiguity',()=>assert.equal(claim(base,{...state(),tool_policy:'unknown'},0).reason,'QUOTA_OR_TOOL_POLICY_UNVERIFIED'));
t('malformed state',()=>assert.equal(claim(base,{runs:'0',seen:[],gate:false,recovery_required:false},0).reason,'MALFORMED_STATE'));
t('lease heartbeat',()=>{const s=state();claim({...base,job_id:'lease'},s,0);assert.equal(heartbeat(s,'lease',1).status,'PASS');assert.equal(heartbeat(s,'lease',40000).reason,'RECOVERY_REQUIRED')});
t('concurrent run',()=>{const s=state();claim({...base,job_id:'active'},s,0);assert.equal(claim({...base,job_id:'other',idempotency_key:'z'.repeat(16)},s,1).reason,'CONCURRENT_RUN')});
t('recovery requires verification',()=>{const s={recovery_required:true};assert.equal(recover(s,false).reason,'RECOVERY_NOT_VERIFIED');assert.equal(recover(s,true).status,'PASS')});
t('max bounded runs',()=>{const s=state();for(let i=0;i<MAX_RUNS;i++){s.lease=null;assert.equal(claim({...base,job_id:`r${i}`,idempotency_key:`${'r'.repeat(15)}${i}`},s,0).status,'PASS')}s.lease=null;assert.equal(claim({...base,job_id:'rX',idempotency_key:'x'.repeat(16)},s,0).reason,'MAX_RUNS_REACHED')});
t('persistent atomic state',()=>{const d=fs.mkdtempSync(`${os.tmpdir()}/v31q-`);const s=loadState(d);s.runs=1;saveState(s,d);assert.equal(loadState(d).runs,1);assert.equal(loadState(d).quota,'unknown');assert.equal(fs.statSync(`${d}/state.json`).mode&0o777,0o600);fs.rmSync(d,{recursive:true,force:true})});
