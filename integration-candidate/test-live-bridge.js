'use strict';
const assert = require('assert');
const net = require('net');
const fs = require('fs');
const os = require('os');
const path = require('path');

async function main(){
  const td=fs.mkdtempSync(path.join(os.tmpdir(),'zeus-live-bridge.'));
  const sock=path.join(td,'adapter.sock');
  const server=net.createServer(c=>{
    let b=''; c.setEncoding('utf8');
    c.on('data',x=>{b+=x; const i=b.indexOf('\n'); if(i<0)return; const r=JSON.parse(b.slice(0,i));
      c.end(JSON.stringify({status:r.operation==='candidate_preflight'?'PASS':'UNVERIFIED',exit_code:0,operation:r.operation})+'\n');
    });
  });
  await new Promise((res,rej)=>{server.once('error',rej);server.listen(sock,res)});
  const {HostBackendClient}=require('./host-backend-client');
  const client=new HostBackendClient(sock);
  const req={operation:'candidate_preflight',change_id:'V31-TEST-20260903',candidate_root:'/x',expected_hash:'a'.repeat(64),job_id:'job',nonce:'nonce-abcdefghijklmnop',expires_at:new Date(Date.now()+60000).toISOString(),requested_by:'zeus-production',idempotency_key:'idem-abcdefghijklmnop'};
  const r=await client.candidatePreflight(req); assert.equal(r.status,'PASS'); assert.equal(r.exit_code,0);
  server.close(); fs.rmSync(td,{recursive:true,force:true});
  console.log('HOST_BACKEND_CLIENT=PASS');
}
main().catch(e=>{console.error(e);process.exit(1)});
