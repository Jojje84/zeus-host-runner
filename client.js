'use strict';
const crypto=require('crypto');
function makeRequest(operation,change_id,expected_hash,job_id){return {operation,change_id,candidate_root:'/home/umbrel/umbrel/app-data/openclaw/data/zeus-v31-umbrel-candidates-20260902',expected_hash,job_id,nonce:crypto.randomBytes(12).toString('hex'),expires_at:new Date(Date.now()+30000).toISOString(),requested_by:'zeus-production',idempotency_key:`${change_id}:${job_id}`};}
module.exports={makeRequest};
