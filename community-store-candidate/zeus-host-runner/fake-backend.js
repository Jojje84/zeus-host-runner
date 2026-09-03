'use strict';
class FakeBackend {
  constructor(){this.calls=[];this.mode='ok';}
  call(name,args){this.calls.push({name,args});if(this.mode==='timeout') throw Object.assign(new Error('backend timeout'),{code:'ETIMEDOUT'});if(this.mode==='error') throw new Error('backend failure');return {exit_code:0,stdout:`FAKE_${name}_OK`,stderr:''};}
  candidatePreflight(a){return this.call('candidate_preflight',a)}
  buildRescue(a){return this.call('build_rescue',a)}
  inspectImage(a){return this.call('inspect_image',a)}
  runRescueTest(a){return this.call('run_rescue_test',a)}
  cleanupOwnTemp(a){return this.call('cleanup_own_temp',a)}
}
module.exports={FakeBackend};
