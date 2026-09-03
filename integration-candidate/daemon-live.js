'use strict';
const fs = require('fs');
const net = require('net');
const path = require('path');
const {dispatch} = require('./live-adapter');
const {HostBackendClient} = require('./host-backend-client');

const SOCKET_PATH = process.env.RUNNER_SOCKET || '/run/zeus-host-runner/runner.sock';
const STATE_DIR = process.env.RUNNER_STATE_DIR || '/runner-state';
const AUDIT_DIR = process.env.RUNNER_AUDIT_DIR || '/runner-audit';
const HOST_ADAPTER_SOCKET = process.env.ZEUS_HOST_ADAPTER_SOCKET || '/host-adapter/adapter.sock';
const MAX_LINE = 65536;
const backend = new HostBackendClient(HOST_ADAPTER_SOCKET);

function dir(p){ const s=fs.lstatSync(p); if(!s.isDirectory()||s.isSymbolicLink()) throw Error('WRITE_DIR_INVALID'); }
function file(p){ try { const s=fs.lstatSync(p); if(s.isSymbolicLink()||!s.isFile()) throw Error('WRITE_FILE_INVALID'); } catch(e){ if(e.code!=='ENOENT') throw e; } }
function audit(e){ dir(AUDIT_DIR); const p=path.join(AUDIT_DIR,'runner-audit.jsonl'); file(p); fs.appendFileSync(p,JSON.stringify(e)+'\n',{mode:0o640}); }
function state(e){
  dir(STATE_DIR); const p=path.join(STATE_DIR,'last-result.json'); file(p);
  const t=`${p}.tmp-${process.pid}-${Date.now()}`;
  fs.writeFileSync(t,JSON.stringify(e)+'\n',{mode:0o640,flag:'wx'}); fs.renameSync(t,p);
}
function fail(reason,exit_code=64){ return {status:'FAIL',exit_code,reason}; }

async function handle(line){
  if(Buffer.byteLength(line,'utf8')>MAX_LINE) return fail('REQUEST_TOO_LARGE');
  let r; try { r=JSON.parse(line); } catch(_) { return fail('INVALID_JSON'); }
  if(r && r.probe==='liveness' && Object.keys(r).length===1) return {status:'PASS',liveness:'PASS',readiness:'UNVERIFIED',mutation_gate:false};
  const started=new Date().toISOString();
  try {
    const result=await dispatch(r,backend);
    const record={...result,received_at:started,finished_at:new Date().toISOString()};
    audit({event:'request_result',operation:r&&r.operation||null,job_id:r&&r.job_id||null,status:record.status,exit_code:record.exit_code,backend_called:record.backend_called===true});
    state(record); return record;
  } catch(_) { return fail('BROKER_FAILURE',70); }
}

function start(){
  dir(path.dirname(SOCKET_PATH)); dir(STATE_DIR); dir(AUDIT_DIR);
  try { const s=fs.lstatSync(SOCKET_PATH); if(!s.isSocket()||s.isSymbolicLink()) throw Error('SOCKET_PATH_INVALID'); fs.unlinkSync(SOCKET_PATH); }
  catch(e){ if(e.code!=='ENOENT') throw e; }
  process.umask(0o007);
  const server=net.createServer(c=>{
    let b=''; let chain=Promise.resolve(); c.setEncoding('utf8');
    c.on('data',x=>{
      b+=x;
      if(Buffer.byteLength(b,'utf8')>MAX_LINE){ c.end(JSON.stringify(fail('REQUEST_TOO_LARGE'))+'\n'); return; }
      let i;
      while((i=b.indexOf('\n'))>=0){
        const line=b.slice(0,i); b=b.slice(i+1);
        chain=chain.then(()=>handle(line)).then(r=>{ if(!c.destroyed) c.write(JSON.stringify(r)+'\n'); });
      }
    });
    c.on('error',()=>{});
  });
  server.listen(SOCKET_PATH,()=>{
    try { fs.chmodSync(SOCKET_PATH,0o660); audit({event:'daemon_ready',socket:SOCKET_PATH,host_adapter_socket:HOST_ADAPTER_SOCKET}); }
    catch(_){ server.close(); process.exitCode=70; }
  });
  const stop=()=>server.close(()=>{try{fs.unlinkSync(SOCKET_PATH)}catch(_){} process.exit(0);});
  process.on('SIGTERM',stop); process.on('SIGINT',stop);
}
if(require.main===module) start();
module.exports={handle,start,SOCKET_PATH,STATE_DIR,AUDIT_DIR,HOST_ADAPTER_SOCKET};
