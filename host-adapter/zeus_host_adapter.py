#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import socket
import struct
import subprocess
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_REQUEST = 64 * 1024
SO_PEERCRED_LEN = struct.calcsize('3i')
OPS = {'candidate_preflight','build_rescue','inspect_image','run_rescue_test','cleanup_own_temp'}
MUTATING_OPS = {'build_rescue','run_rescue_test','cleanup_own_temp'}
REQUIRED_KEYS = {'operation','change_id','candidate_root','expected_hash','job_id','nonce','expires_at','requested_by','idempotency_key'}
CHANGE_RE = re.compile(r'^V31-[A-Z0-9-]{8,64}$')
TOKEN_RE = re.compile(r'^[A-Za-z0-9._:-]{16,128}$')
JOB_RE = re.compile(r'^[A-Za-z0-9._-]{1,80}$')
HEX64_RE = re.compile(r'^[0-9a-f]{64}$')
IMAGE_RE = re.compile(r'^sha256:[0-9a-f]{64}$')
REDACT_RE = re.compile(r'(?i)(token|password|secret|api[_-]?key|authorization)\s*[:=]\s*[^\s,}]+')

class FailClosed(Exception):
    def __init__(self, reason: str, exit_code: int = 65):
        super().__init__(reason); self.reason = reason; self.exit_code = exit_code

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace('+00:00','Z')

def redact(value: str) -> str:
    return REDACT_RE.sub(lambda m: f'{m.group(1)}=[REDACTED]', value or '')

def sha256_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''): h.update(chunk)
    return h.hexdigest()

def atomic_json(path: Path, obj: dict[str,Any]) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=f'.{path.name}.',dir=path.parent)
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            json.dump(obj,f,sort_keys=True,separators=(',',':')); f.write('\n'); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,path)
    finally:
        try: os.unlink(tmp)
        except FileNotFoundError: pass

def append_audit(path: Path, event: dict[str,Any]) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    fd=os.open(path,os.O_APPEND|os.O_CREAT|os.O_WRONLY,0o640)
    try:
        os.write(fd,(json.dumps(event,sort_keys=True,separators=(',',':'))+'\n').encode()); os.fsync(fd)
    finally: os.close(fd)

class Config:
    def __init__(self) -> None:
        self.socket_path=Path(os.environ.get('ZEUS_HOST_ADAPTER_SOCKET','/run/zeus-host-adapter/adapter.sock'))
        self.state_dir=Path(os.environ.get('ZEUS_HOST_ADAPTER_STATE','/var/lib/zeus-host-adapter'))
        self.audit_path=self.state_dir/'audit'/'host-adapter.jsonl'; self.state_path=self.state_dir/'state.json'; self.runs_dir=self.state_dir/'runs'
        self.allowed_uid=self._required_int('ZEUS_RUNNER_UID'); self.allowed_gid=self._required_int('ZEUS_RUNNER_GID')
        self.rescue_uid=self._required_int('ZEUS_RESCUE_UID'); self.rescue_gid=self._required_int('ZEUS_RESCUE_GID')
        self.candidate_root=Path(os.environ.get('ZEUS_ALLOWED_CANDIDATE_ROOT','/home/umbrel/umbrel/app-data/openclaw/data/zeus-v31-umbrel-candidates-20260902'))
        self.docker=os.environ.get('ZEUS_DOCKER_BIN','/usr/bin/docker')
        self.max_runs_per_change=int(os.environ.get('ZEUS_MAX_RUNS_PER_CHANGE','6'))
        if min(self.allowed_uid,self.allowed_gid,self.rescue_uid,self.rescue_gid)<1000: raise SystemExit('UID/GID must be non-privileged >=1000')
        if not Path(self.docker).is_file(): raise SystemExit('docker binary missing')
    @staticmethod
    def _required_int(name: str) -> int:
        raw=os.environ.get(name)
        if raw is None or not raw.isdigit(): raise SystemExit(f'{name} missing/invalid')
        return int(raw)

class StateStore:
    def __init__(self,cfg:Config):
        self.cfg=cfg; self.lock=threading.Lock(); self.state=self._load()
        if self.state.get('lease') is not None:
            self.state['lease']=None; self.state['recovery_required']=True; self._save()
    def _load(self):
        try: data=json.loads(self.cfg.state_path.read_text())
        except FileNotFoundError: data={}
        except Exception as e: raise SystemExit(f'state unreadable: {e}')
        return {'seen':list(data.get('seen',[]))[-512:],'run_counts':dict(data.get('run_counts',{})),'lease':data.get('lease'),'recovery_required':bool(data.get('recovery_required',False)),'last_image_id':data.get('last_image_id'),'last_change_id':data.get('last_change_id'),'last_job_id':data.get('last_job_id')}
    def _save(self): atomic_json(self.cfg.state_path,self.state)
    def claim(self,req):
        with self.lock:
            if self.state['recovery_required']: raise FailClosed('RECOVERY_REQUIRED',65)
            if req['idempotency_key'] in self.state['seen']: raise FailClosed('DUPLICATE_IDEMPOTENCY_KEY',65)
            count=int(self.state['run_counts'].get(req['change_id'],0))
            if count>=self.cfg.max_runs_per_change: raise FailClosed('MAX_RUNS_REACHED',65)
            if self.state['lease'] is not None: raise FailClosed('CONCURRENT_RUN',65)
            self.state['seen'].append(req['idempotency_key']); self.state['seen']=self.state['seen'][-512:]
            self.state['run_counts'][req['change_id']]=count+1
            if req['operation'] in MUTATING_OPS: self.state['lease']={'change_id':req['change_id'],'job_id':req['job_id'],'started_at':utc_now()}
            self._save()
    def finish(self,req,image_id=None):
        with self.lock:
            if image_id is not None:
                self.state['last_image_id']=image_id; self.state['last_change_id']=req['change_id']; self.state['last_job_id']=req['job_id']
            self.state['lease']=None; self._save()
    def fail_mutation(self):
        with self.lock:
            self.state['lease']=None; self.state['recovery_required']=True; self._save()
    def last_image(self,req):
        with self.lock:
            image=self.state.get('last_image_id')
            if not image or self.state.get('last_change_id')!=req['change_id']: raise FailClosed('IMAGE_ID_UNBOUND',65)
            if not IMAGE_RE.fullmatch(image): raise FailClosed('IMAGE_ID_INVALID_STATE',65)
            return image

class HostAdapter:
    def __init__(self,cfg:Config,state:StateStore,runner=subprocess.run): self.cfg=cfg; self.state=state; self.runner=runner
    def validate_request(self,req):
        if not isinstance(req,dict) or set(req)!=REQUIRED_KEYS: raise FailClosed('SCHEMA_EXTRA_OR_MISSING_FIELD',64)
        if any(not isinstance(req[k],str) for k in REQUIRED_KEYS): raise FailClosed('SCHEMA_FIELD_INVALID',64)
        if req['operation'] not in OPS: raise FailClosed('OPERATION_NOT_ALLOWLISTED',64)
        if not CHANGE_RE.fullmatch(req['change_id']): raise FailClosed('CHANGE_ID_INVALID',64)
        if not JOB_RE.fullmatch(req['job_id']): raise FailClosed('JOB_ID_INVALID',64)
        if not TOKEN_RE.fullmatch(req['nonce']) or not TOKEN_RE.fullmatch(req['idempotency_key']): raise FailClosed('NONCE_OR_IDEMPOTENCY_INVALID',64)
        if not HEX64_RE.fullmatch(req['expected_hash']): raise FailClosed('EXPECTED_HASH_INVALID',64)
        if req['requested_by']!='zeus-production': raise FailClosed('REQUESTER_REJECTED',64)
        if Path(req['candidate_root'])!=self.cfg.candidate_root: raise FailClosed('CANDIDATE_PATH_REJECTED',64)
        try:
            exp=datetime.fromisoformat(req['expires_at'].replace('Z','+00:00'))
            if exp.tzinfo is None or exp<=datetime.now(timezone.utc): raise ValueError
        except ValueError: raise FailClosed('JOB_EXPIRED',64)
        return req
    def verify_candidate(self,req):
        root=self.cfg.candidate_root
        if not root.is_dir() or root.is_symlink(): raise FailClosed('CANDIDATE_ROOT_INVALID',65)
        manifest=root/'ARTIFACT-HASHES.sha256'
        if not manifest.is_file() or manifest.is_symlink(): raise FailClosed('CANDIDATE_MANIFEST_INVALID',65)
        actual=sha256_file(manifest)
        if actual!=req['expected_hash']: raise FailClosed('CANDIDATE_HASH_MISMATCH',65)
        try: lines=manifest.read_text(encoding='utf-8').splitlines()
        except Exception: raise FailClosed('CANDIDATE_MANIFEST_UNREADABLE',65)
        if not lines: raise FailClosed('CANDIDATE_MANIFEST_EMPTY',65)
        entries={}
        for line in lines:
            m=re.fullmatch(r'([0-9a-f]{64})  ([^\x00\r\n]+)',line)
            if not m: raise FailClosed('CANDIDATE_MANIFEST_FORMAT',65)
            digest,rel=m.groups(); rel_path=Path(rel)
            if rel_path.is_absolute() or '..' in rel_path.parts or rel in entries: raise FailClosed('CANDIDATE_MANIFEST_PATH_INVALID',65)
            target=root/rel_path
            try: st=target.lstat()
            except FileNotFoundError: raise FailClosed('CANDIDATE_FILE_MISSING',65)
            if target.is_symlink() or not target.is_file(): raise FailClosed('CANDIDATE_FILE_TYPE_INVALID',65)
            if sha256_file(target)!=digest: raise FailClosed('CANDIDATE_FILE_HASH_MISMATCH',65)
            entries[rel]=digest
        return actual,entries
    def _run(self,argv,timeout):
        return self.runner(argv,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=timeout,check=False,close_fds=True)
    def candidate_preflight(self,req):
        actual,_=self.verify_candidate(req); return {'status':'PASS','exit_code':0,'artifact_hashes':[actual]}
    def build_rescue(self,req):
        _,entries=self.verify_candidate(req)
        ctx=self.cfg.candidate_root/'zeus-rescue'/'build-context'; expected={'BUILD-METADATA.json','Dockerfile','operations.allowlist','rescue-controller.js'}
        bound={f'zeus-rescue/build-context/{name}' for name in expected}
        if not bound.issubset(entries): raise FailClosed('RESCUE_CONTEXT_NOT_MANIFEST_BOUND',65)
        if not ctx.is_dir() or ctx.is_symlink(): raise FailClosed('RESCUE_CONTEXT_INVALID',65)
        names={p.name for p in ctx.iterdir() if p.is_file() and not p.is_symlink()}
        if names!=expected or any(p.is_dir() for p in ctx.iterdir()): raise FailClosed('RESCUE_CONTEXT_ALLOWLIST_MISMATCH',65)
        run_dir=self.cfg.runs_dir/req['change_id']/req['job_id']
        if run_dir.exists(): raise FailClosed('RUN_DIR_ALREADY_EXISTS',65)
        run_dir.mkdir(parents=True,mode=0o700); iid=run_dir/'image.iid'
        cp=self._run([self.cfg.docker,'build','--pull=false','--iidfile',str(iid),'--label',f'zeus.change_id={req["change_id"]}','--label',f'zeus.job_id={req["job_id"]}',str(ctx)],240)
        if cp.returncode!=0: raise FailClosed('DOCKER_BUILD_FAILED',70)
        if not iid.is_file() or iid.is_symlink(): raise FailClosed('IIDFILE_INVALID',70)
        image_id=iid.read_text().strip()
        if not IMAGE_RE.fullmatch(image_id): raise FailClosed('IMAGE_ID_INVALID',70)
        inspect=self._run([self.cfg.docker,'image','inspect',image_id,'--format','{{.Id}}'],30)
        if inspect.returncode!=0 or inspect.stdout.strip()!=image_id: raise FailClosed('IMAGE_ID_INSPECT_MISMATCH',70)
        return {'status':'UNVERIFIED','exit_code':0,'immutable_image_id':image_id,'stdout':'BUILD_COMPLETE_IMAGE_ID_BOUND'}
    def inspect_image(self,req):
        image_id=self.state.last_image(req)
        cp=self._run([self.cfg.docker,'image','inspect',image_id,'--format','{{.Id}} {{json .RepoDigests}}'],30)
        if cp.returncode!=0: raise FailClosed('IMAGE_INSPECT_FAILED',70)
        if cp.stdout.strip().split(' ',1)[0]!=image_id: raise FailClosed('IMAGE_ID_INSPECT_MISMATCH',70)
        return {'status':'PASS','exit_code':0,'immutable_image_id':image_id,'stdout':redact(cp.stdout.strip())}
    def run_rescue_test(self,req):
        image_id=self.state.last_image(req)
        base=[self.cfg.docker,'run','--rm','--network','none','--user',f'{self.cfg.rescue_uid}:{self.cfg.rescue_gid}','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges:true','--cpus','0.50','--memory','128m','--pids-limit','64','--tmpfs','/tmp:size=16m,noexec,nosuid,nodev',image_id]
        evidence=[]
        for op,expected in [('health',0),('unknown_op',64),('start_production',65)]:
            cp=self._run(base+[op],45); evidence.append({'operation':op,'expected_exit':expected,'actual_exit':cp.returncode})
            if cp.returncode!=expected: raise FailClosed(f'RESCUE_TEST_MISMATCH_{op.upper()}',70)
        return {'status':'PASS','exit_code':0,'immutable_image_id':image_id,'tests':evidence}
    def cleanup_own_temp(self,req):
        target=self.cfg.runs_dir/req['change_id']/req['job_id']; rr=self.cfg.runs_dir.resolve(strict=False); tr=target.resolve(strict=False)
        if rr not in tr.parents: raise FailClosed('CLEANUP_PATH_REJECTED',65)
        if target.exists():
            if target.is_symlink(): raise FailClosed('CLEANUP_SYMLINK_REJECTED',65)
            shutil.rmtree(target)
        return {'status':'PASS','exit_code':0,'stdout':'OWN_TEMP_CLEANED'}
    def execute(self,req_raw):
        started=utc_now(); req=self.validate_request(req_raw); self.state.claim(req)
        try:
            body=getattr(self,req['operation'])(req)
            self.state.finish(req,body.get('immutable_image_id') if req['operation']=='build_rescue' else None)
            result={'operation':req['operation'],'job_id':req['job_id'],'change_id':req['change_id'],'status':body.get('status','UNVERIFIED'),'exit_code':body.get('exit_code',0),'immutable_image_id':body.get('immutable_image_id'),'artifact_hashes':body.get('artifact_hashes',[]),'stdout':redact(body.get('stdout','')),'stderr':redact(body.get('stderr','')),'started_at':started,'finished_at':utc_now()}
            if 'tests' in body: result['tests']=body['tests']
            return result
        except Exception:
            if req['operation'] in MUTATING_OPS: self.state.fail_mutation()
            raise

class Server:
    def __init__(self,cfg,adapter): self.cfg=cfg; self.adapter=adapter
    def _peer(self,conn): return struct.unpack('3i',conn.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,SO_PEERCRED_LEN))
    def _respond(self,conn,payload): conn.sendall((json.dumps(payload,sort_keys=True,separators=(',',':'))+'\n').encode())
    def handle(self,conn):
        try:
            pid,uid,gid=self._peer(conn)
            if uid!=self.cfg.allowed_uid:
                self._respond(conn,{'status':'FAIL','exit_code':77,'reason':'PEER_UID_REJECTED'}); append_audit(self.cfg.audit_path,{'event':'peer_rejected','pid':pid,'uid':uid,'gid':gid,'at':utc_now()}); return
            data=b''
            while b'\n' not in data:
                chunk=conn.recv(4096)
                if not chunk: raise FailClosed('EMPTY_REQUEST',64)
                data+=chunk
                if len(data)>MAX_REQUEST: raise FailClosed('REQUEST_TOO_LARGE',64)
            line,_,extra=data.partition(b'\n')
            if extra.strip(): raise FailClosed('MULTIPLE_REQUESTS_REJECTED',64)
            try: req=json.loads(line.decode())
            except Exception: raise FailClosed('INVALID_JSON',64)
            result=self.adapter.execute(req); self._respond(conn,result)
            append_audit(self.cfg.audit_path,{'event':'request_result','peer_pid':pid,'peer_uid':uid,'peer_gid':gid,'operation':req.get('operation'),'job_id':req.get('job_id'),'status':result.get('status'),'exit_code':result.get('exit_code'),'at':utc_now()})
        except FailClosed as e: self._respond(conn,{'status':'FAIL','exit_code':e.exit_code,'reason':e.reason})
        except Exception as e:
            self._respond(conn,{'status':'UNVERIFIED','exit_code':70,'reason':'BROKER_FAILURE'}); append_audit(self.cfg.audit_path,{'event':'broker_failure','reason':type(e).__name__,'at':utc_now()})
        finally: conn.close()
    def serve(self):
        path=self.cfg.socket_path; path.parent.mkdir(parents=True,exist_ok=True); os.chmod(path.parent,0o770)
        try:
            st=path.lstat()
            if not stat_is_socket(st.st_mode) or path.is_symlink(): raise SystemExit('existing adapter socket path unsafe')
            path.unlink()
        except FileNotFoundError: pass
        sock=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM); sock.bind(str(path)); os.chown(path,0,self.cfg.allowed_gid); os.chmod(path,0o660); sock.listen(16)
        append_audit(self.cfg.audit_path,{'event':'adapter_ready','socket':str(path),'at':utc_now()})
        while True:
            conn,_=sock.accept(); threading.Thread(target=self.handle,args=(conn,),daemon=True).start()

def stat_is_socket(mode:int)->bool:
    import stat; return stat.S_ISSOCK(mode)

def main():
    cfg=Config(); cfg.state_dir.mkdir(parents=True,exist_ok=True); os.chmod(cfg.state_dir,0o700); state=StateStore(cfg); Server(cfg,HostAdapter(cfg,state)).serve()

if __name__=='__main__': main()
