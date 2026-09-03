'use strict';
const assert=require('assert');const {check}=require('./readiness');
const base={liveness:'PASS',socket_path_valid:true,state_dir_valid:true,audit_dir_valid:true,image_id_bound:true,recovery_required:false,policy_ambiguous:false};
function c(n,f){try{f();console.log(`${n}: PASS`)}catch(e){console.log(`${n}: FAIL ${e.message}`);process.exitCode=1}}
c('ready is non-mutating',()=>{const r=check(base);assert.equal(r.exit_code,0);assert.equal(r.mutation_gate,false)});
c('liveness failure',()=>assert.equal(check({...base,liveness:'UNVERIFIED'}).exit_code,10));
c('recovery blocks readiness',()=>assert.equal(check({...base,recovery_required:true}).exit_code,12));
c('path failure',()=>assert.equal(check({...base,socket_path_valid:false}).exit_code,11));
c('image unbound',()=>assert.equal(check({...base,image_id_bound:false}).exit_code,13));
c('policy ambiguity',()=>assert.equal(check({...base,policy_ambiguous:true}).exit_code,14));
