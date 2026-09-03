'use strict';
const fs=require('fs');
const crypto=require('crypto');
const schema=require('./runner-schema.json');
const policy=require('./operations.allowlist.json');
const PREFIX='/home/umbrel/umbrel/app-data/openclaw/data/zeus-v31-umbrel-candidates-20260902';
const seen=new Map();
function fail(code,reason,extra={}){return {status:'FAIL',exit_code:code,reason,...extra};}
function validate(r,now=new Date()){
  if(!r||typeof r!=='object'||Object.keys(r).some(k=>!schema.required.includes(k))) return fail(64,'SCHEMA_EXTRA_OR_MISSING_FIELD');
  for(const k of schema.required) if(typeof r[k]!=='string') return fail(64,'SCHEMA_FIELD_INVALID', {field:k});
  if(!Object.keys(policy.operations).includes(r.operation)) return fail(64,'OPERATION_NOT_ALLOWLISTED');
  if(r.candidate_root!==PREFIX||r.candidate_root.includes('..')||r.candidate_root.includes('\0')) return fail(64,'CANDIDATE_PATH_REJECTED');
  if(!/^[0-9a-f]{64}$/.test(r.expected_hash)) return fail(64,'EXPECTED_HASH_INVALID');
  if(r.requested_by!=='zeus-production') return fail(64,'REQUESTER_REJECTED');
  const exp=Date.parse(r.expires_at); if(!Number.isFinite(exp)||exp<=now.getTime()) return fail(64,'JOB_EXPIRED');
  if(seen.has(r.idempotency_key)) return fail(65,'DUPLICATE_IDEMPOTENCY_KEY');
  return {status:'PASS'};
}
function redact(s){return String(s).replace(/(token|password|secret|api[_-]?key|authorization)\s*[:=]\s*[^\s,}]+/gi,'$1=[REDACTED]');}
function result(r, started, body){return {operation:r.operation,job_id:r.job_id,change_id:r.change_id,exit_code:body.exit_code??0,status:body.status||'UNVERIFIED',stdout:redact(body.stdout||''),stderr:redact(body.stderr||''),artifact_hashes:body.artifact_hashes||[],immutable_image_id:body.immutable_image_id||null,runtime_hardening:body.runtime_hardening||'UNVERIFIED',started_at:started,finished_at:new Date().toISOString()};}
function executeMock(r,now=new Date()){
  const v=validate(r,now),started=now.toISOString(); if(v.status==='FAIL') return result(r,started,v);
  seen.set(r.idempotency_key,Date.now());
  if(r.operation==='candidate_preflight') return result(r,started,{status:'PASS',stdout:'HASH_AND_CONTEXT_PREFLIGHT_OK'});
  if(r.operation==='inspect_image') return result(r,started,{status:'UNVERIFIED',stderr:'HOST_IMAGE_INSPECT_NOT_CONNECTED'});
  if(r.operation==='run_rescue_test') return result(r,started,{status:'UNVERIFIED',stderr:'HOST_RUNTIME_NOT_CONNECTED'});
  return result(r,started,{status:'UNVERIFIED',stderr:'HOST_EXECUTOR_NOT_CONNECTED'});
}
if(require.main===module){let line;while((line=process.stdin.read())!==null){try{const r=JSON.parse(line);process.stdout.write(JSON.stringify(executeMock(r))+'\n');}catch(e){process.stdout.write(JSON.stringify(fail(64,'INVALID_JSON'))+'\n');}}}
module.exports={validate,redact,executeMock,PREFIX};
