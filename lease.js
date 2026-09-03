'use strict';
class Lease {
  constructor(timeoutMs=1000){this.timeoutMs=timeoutMs;this.owner=null;this.expires=0;this.state='free';}
  acquire(owner,now=Date.now()){if(this.state==='recovery_required')return {ok:false,state:this.state};if(this.owner&&now<this.expires)return {ok:false,state:'busy'};this.owner=owner;this.expires=now+this.timeoutMs;this.state='leased';return {ok:true,state:this.state};}
  heartbeat(owner,now=Date.now()){if(this.owner!==owner||this.state!=='leased')return {ok:false,state:'recovery_required'};this.expires=now+this.timeoutMs;return {ok:true,state:this.state};}
  expire(now=Date.now()){if(this.state==='leased'&&now>=this.expires){this.state='recovery_required';this.owner=null;}return {ok:false,state:this.state};}
  recover(verified){if(this.state!=='recovery_required'||!verified)return {ok:false,state:this.state};this.state='free';return {ok:true,state:this.state};}
}
module.exports={Lease};
