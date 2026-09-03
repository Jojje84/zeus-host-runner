'use strict';
const {validate} = require('../runner');
const METHODS = {
  candidate_preflight:'candidatePreflight',
  build_rescue:'buildRescue',
  inspect_image:'inspectImage',
  run_rescue_test:'runRescueTest',
  cleanup_own_temp:'cleanupOwnTemp',
};

async function dispatch(request, backend, now = new Date()) {
  const checked = validate(request, now);
  if (checked.status === 'FAIL') return {...checked, backend_called:false};
  const method = METHODS[request.operation];
  if (!method || typeof backend[method] !== 'function') {
    return {status:'UNVERIFIED', exit_code:70, reason:'BACKEND_METHOD_UNAVAILABLE', backend_called:false};
  }
  try {
    const result = await backend[method](request);
    if (!result || typeof result !== 'object' || !['PASS','FAIL','UNVERIFIED','RECOVERY_REQUIRED'].includes(result.status) || !Number.isInteger(result.exit_code)) {
      return {status:'UNVERIFIED', exit_code:70, reason:'BACKEND_RESPONSE_INVALID', backend_called:true};
    }
    return {...result, backend_called:true};
  } catch (e) {
    return {status:'UNVERIFIED', exit_code:e && e.code === 'ETIMEDOUT' ? 124 : 70,
      reason:e && e.code === 'ETIMEDOUT' ? 'BACKEND_TIMEOUT' : 'BACKEND_FAILURE', backend_called:true};
  }
}
module.exports = {dispatch, METHODS};
