'use strict';
const {validate}=require('./runner');
const METHODS={candidate_preflight:'candidatePreflight',build_rescue:'buildRescue',inspect_image:'inspectImage',run_rescue_test:'runRescueTest',cleanup_own_temp:'cleanupOwnTemp'};
function dispatch(request,backend,now=new Date()){
  const checked=validate(request,now); if(checked.status==='FAIL') return {...checked,backend_called:false};
  const method=METHODS[request.operation]; if(!method||typeof backend[method]!=='function') return {status:'UNVERIFIED',exit_code:70,reason:'BACKEND_METHOD_UNAVAILABLE',backend_called:false};
  try { const b=backend[method]({job_id:request.job_id,change_id:request.change_id,candidate_root:request.candidate_root,expected_hash:request.expected_hash}); return {...b,status:b.exit_code===0?'UNVERIFIED':'FAIL',backend_called:true}; }
  catch(e){return {status:'UNVERIFIED',exit_code:e.code==='ETIMEDOUT'?124:70,reason:e.code==='ETIMEDOUT'?'BACKEND_TIMEOUT':'BACKEND_FAILURE',backend_called:true};}
}
module.exports={dispatch,METHODS};
