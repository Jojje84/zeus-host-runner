'use strict';
const fs=require('fs');
const path=require('path');
const ROOT='/data/zeus-v31-work-queue';
const SESSION='zeus-v31-canonical';
const MAX_RUNS=6;
function loadState(root=ROOT){const p=path.join(root,'state.json');try{return JSON.parse(fs.readFileSync(p,'utf8'));}catch(e){if(e.code==='ENOENT')return {session:SESSION,runs:0,seen:[],gate:false,recovery_required:false,quota:'unknown',tool_policy:'unknown',lease:null};throw e;}}
function saveState(state,root=ROOT){if(state.session&&state.session!==SESSION)throw new Error('SESSION_REJECTED');fs.mkdirSync(root,{recursive:true});const p=path.join(root,'state.json');const t=`${p}.tmp-${process.pid}`;fs.writeFileSync(t,JSON.stringify({...state,session:SESSION})+'\n',{mode:0o600});fs.renameSync(t,p);return p;}
function fail(code,reason){return {status:'FAIL',exit_code:code,reason};}
function validate(job,now=Date.now()){
  const keys=['job_id','session','change_id','idempotency_key','expires_at','requested_by','work_kind'];
  if(!job||Object.keys(job).some(k=>!keys.includes(k))||keys.some(k=>typeof job[k]!=='string'))return fail(64,'SCHEMA_REJECTED');
  if(job.session!==SESSION||job.requested_by!=='zeus-production')return fail(64,'SESSION_OR_REQUESTER_REJECTED');
  if(job.work_kind!=='continue')return fail(65,'JORGE_GATE_OR_UNSUPPORTED_WORK');
  if(!/^V31-[A-Z0-9-]{8,64}$/.test(job.change_id)||!/^[A-Za-z0-9._:-]{16,128}$/.test(job.idempotency_key))return fail(64,'IDENTITY_REJECTED');
  if(!Number.isFinite(Date.parse(job.expires_at))||Date.parse(job.expires_at)<=now)return fail(64,'EXPIRED');
  return {status:'PASS'};
}
function claim(job,state,now=Date.now()){
  const v=validate(job,now);if(v.status==='FAIL')return v;
  if(!state||!Number.isInteger(state.runs)||!Array.isArray(state.seen)||typeof state.gate!=='boolean'||typeof state.recovery_required!=='boolean')return fail(65,'MALFORMED_STATE');
  if(state.quota!=='verified'||state.tool_policy!=='approved')return fail(65,'QUOTA_OR_TOOL_POLICY_UNVERIFIED');
  if(state.lease&&state.lease.expires_at>now)return fail(65,'CONCURRENT_RUN');
  if(state.gate||state.recovery_required)return fail(65,state.gate?'JORGE_DECISION_REQUIRED':'RECOVERY_REQUIRED');
  if(state.runs>=MAX_RUNS)return fail(65,'MAX_RUNS_REACHED');
  if(state.seen.includes(job.idempotency_key))return fail(65,'DUPLICATE');
  state.seen.push(job.idempotency_key);state.runs++;state.lease={job_id:job.job_id,expires_at:now+30000};return {status:'PASS',state};
}
function heartbeat(state,jobId,now=Date.now()){if(!state.lease||state.lease.job_id!==jobId||now>=state.lease.expires_at){state.recovery_required=true;return fail(65,'RECOVERY_REQUIRED');}state.lease.expires_at=now+30000;return {status:'PASS',state};}
function recover(state,verified){if(!state.recovery_required||!verified)return fail(65,'RECOVERY_NOT_VERIFIED');state.recovery_required=false;state.lease=null;return {status:'PASS',state};}
module.exports={ROOT,SESSION,MAX_RUNS,validate,claim,heartbeat,recover,loadState,saveState};
