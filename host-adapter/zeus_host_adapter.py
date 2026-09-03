#!/usr/bin/env python3
from __future__ import annotations
import datetime as dt, hashlib, json, os, re, shutil, socket, stat, struct, subprocess, sys, tempfile
from pathlib import Path

ROOT=Path("/home/umbrel/umbrel/app-data/openclaw/data/zeus-v31-umbrel-candidates-20260902")
MANIFEST="ARTIFACT-HASHES.sha256"
RESCUE=Path("zeus-rescue/build-context")
RESCUE_FILES=("BUILD-METADATA.json","Dockerfile","operations.allowlist","rescue-controller.js")
STATE_ROOT=Path("/var/lib/zeus-host-adapter"); WORK=STATE_ROOT/"work"; STATE=STATE_ROOT/"state.json"
AUDIT=Path("/var/log/zeus-host-adapter/audit.jsonl")
MAX=65536
OPS={"candidate_preflight","build_rescue","inspect_image","run_rescue_test","cleanup_own_temp"}
FIELDS=("operation","change_id","candidate_root","expected_hash","job_id","nonce","expires_at","requested_by","idempotency_key")
HEX=re.compile(r"^[0-9a-f]{64}$"); CHANGE=re.compile(r"^V31-[A-Z0-9-]{8,64}$")
TOKEN=re.compile(r"^[A-Za-z0-9._:-]{1,128}$"); JOB=re.compile(r"^[A-Za-z0-9._-]{1,80}$")

class Stop(Exception):
    def __init__(self,reason,code=65,status="FAIL"): self.reason=reason; self.code=code; self.status=status

def now(): return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00","Z")
def sha(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""): h.update(b)
    return h.hexdigest()

def reg(p,uid=None,mode=None):
    try: s=p.lstat()
    except FileNotFoundError: raise Stop(f"MISSING:{p}",66)
    if stat.S_ISLNK(s.st_mode) or not stat.S_ISREG(s.st_mode) or s.st_nlink!=1: raise Stop(f"TYPE_REJECTED:{p}",66)
    if uid is not None and s.st_uid!=uid: raise Stop(f"OWNER_REJECTED:{p}",66)
    if mode is not None and stat.S_IMODE(s.st_mode)&~mode: raise Stop(f"MODE_REJECTED:{p}",66)
    return s

def direc(p,uid=None,mode=None):
    try: s=p.lstat()
    except FileNotFoundError: raise Stop(f"MISSING_DIR:{p}",66)
    if stat.S_ISLNK(s.st_mode) or not stat.S_ISDIR(s.st_mode): raise Stop(f"DIR_TYPE_REJECTED:{p}",66)
    if uid is not None and s.st_uid!=uid: raise Stop(f"DIR_OWNER_REJECTED:{p}",66)
    if mode is not None and stat.S_IMODE(s.st_mode)&~mode: raise Stop(f"DIR_MODE_REJECTED:{p}",66)
    return s

def atomic(p,data,mode=0o600):
    direc(p.parent,0,0o700)
    fd,n=tempfile.mkstemp(prefix="."+p.name+".",dir=p.parent); t=Path(n)
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,"wb") as f: f.write(data); f.flush(); os.fsync(f.fileno())
        os.replace(t,p)
        d=os.open(p.parent,os.O_DIRECTORY)
        try: os.fsync(d)
        finally: os.close(d)
    finally:
        try:t.unlink()
        except FileNotFoundError:pass

def audit(x):
    direc(AUDIT.parent,0,0o750)
    if AUDIT.exists(): reg(AUDIT,0,0o640)
    fd=os.open(AUDIT,os.O_WRONLY|os.O_APPEND|os.O_CREAT|os.O_NOFOLLOW,0o640)
    try: os.write(fd,(json.dumps(x,sort_keys=True,separators=(",",":"))+"\n").encode()); os.fsync(fd)
    finally: os.close(fd)

def save(s): atomic(STATE,(json.dumps(s,sort_keys=True,separators=(",",":"))+"\n").encode())
def load():
    direc(STATE_ROOT,0,0o700)
    if not STATE.exists(): return {"v":1,"seen":[],"images":{},"active":None,"recovery":False}
    reg(STATE,0,0o600)
    try:s=json.loads(STATE.read_text())
    except Exception: raise Stop("STATE_MALFORMED",70)
    if set(s)!={"v","seen","images","active","recovery"} or s["v"]!=1 or not isinstance(s["seen"],list) or not isinstance(s["images"],dict): raise Stop("STATE_SCHEMA_INVALID",70)
    if s["active"] is not None:
        s["active"]=None;s["recovery"]=True;save(s);audit({"at":now(),"event":"stale_active","recovery":True})
    return s

def validate(x):
    if not isinstance(x,dict) or set(x)!=set(FIELDS) or any(not isinstance(x[k],str) for k in FIELDS): raise Stop("SCHEMA_REJECTED",64)
    if x["operation"] not in OPS: raise Stop("OPERATION_NOT_ALLOWLISTED",64)
    if x["candidate_root"]!=str(ROOT): raise Stop("CANDIDATE_PATH_REJECTED",64)
    if not CHANGE.fullmatch(x["change_id"]) or not HEX.fullmatch(x["expected_hash"]) or not JOB.fullmatch(x["job_id"]): raise Stop("IDENTITY_INVALID",64)
    if not TOKEN.fullmatch(x["nonce"]) or len(x["nonce"])<16 or not TOKEN.fullmatch(x["idempotency_key"]) or len(x["idempotency_key"])<16: raise Stop("TOKEN_INVALID",64)
    if x["requested_by"]!="zeus-production": raise Stop("REQUESTER_REJECTED",64)
    try:e=dt.datetime.fromisoformat(x["expires_at"].replace("Z","+00:00"))
    except ValueError: raise Stop("EXPIRES_INVALID",64)
    if e.tzinfo is None or e<=dt.datetime.now(dt.timezone.utc): raise Stop("EXPIRED",64)
    return x

def manifest(expected):
    direc(ROOT); m=ROOT/MANIFEST; reg(m)
    if sha(m)!=expected: raise Stop("MANIFEST_SHA_MISMATCH",68)
    out={}
    for line in m.read_text().splitlines():
        if not line.strip(): continue
        p=line.split(maxsplit=1)
        if len(p)!=2 or not HEX.fullmatch(p[0]): raise Stop("MANIFEST_FORMAT",67)
        rel=p[1].lstrip("*"); q=Path(rel)
        if q.is_absolute() or ".." in q.parts or rel in out: raise Stop("MANIFEST_PATH",67)
        out[rel]=p[0]
    if not out: raise Stop("MANIFEST_EMPTY",67)
    for rel,h in out.items():
        q=ROOT/rel; reg(q); r=q.resolve(strict=True)
        if ROOT not in r.parents or sha(q)!=h: raise Stop("CANDIDATE_FILE_MISMATCH:"+rel,68)
    return out

def docker():
    p=shutil.which("docker",path="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin")
    if not p: raise Stop("DOCKER_CLI_UNAVAILABLE",70,"UNVERIFIED")
    q=Path(p).resolve(strict=True)
    if str(q) not in {"/usr/bin/docker","/usr/local/bin/docker","/usr/sbin/docker"}: raise Stop("DOCKER_CLI_PATH_REJECTED",70,"UNVERIFIED")
    s=reg(q,0)
    if stat.S_IMODE(s.st_mode)&0o022: raise Stop("DOCKER_CLI_WRITABLE",70,"UNVERIFIED")
    return str(q)

def run(a,t=30,cwd=None):
    try:r=subprocess.run(a,cwd=str(cwd) if cwd else None,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=t,shell=False,env={"PATH":"/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin","LANG":"C.UTF-8","HOME":str(STATE_ROOT)})
    except subprocess.TimeoutExpired: raise Stop("HOST_TIMEOUT",124,"UNVERIFIED")
    if len(r.stdout.encode())>MAX or len(r.stderr.encode())>MAX: raise Stop("HOST_OUTPUT_TOO_LARGE",70,"UNVERIFIED")
    return r

def result(r,status,code,reason,**kw):
    z={"operation":r["operation"],"job_id":r["job_id"],"change_id":r["change_id"],"status":status,"exit_code":code,"reason":reason,"finished_at":now()};z.update(kw);return z

def active(r,s):
    if s["recovery"]: raise Stop("RECOVERY_REQUIRED",65)
    if s["active"] is not None: raise Stop("CONCURRENT_OPERATION",65)
    s["active"]={"operation":r["operation"],"job_id":r["job_id"],"change_id":r["change_id"],"at":now()};save(s)
def clear(s): s["active"]=None;save(s)

def workdir(r):
    direc(WORK,0,0o700); n=f'{r["change_id"]}-{r["job_id"]}'
    if not re.fullmatch(r"[A-Za-z0-9._-]{1,160}",n): raise Stop("WORK_ID_INVALID",69)
    w=WORK/n
    if w.exists(): raise Stop("WORK_EXISTS",69)
    w.mkdir(mode=0o700);return w

def stage(entries,w):
    src=ROOT/RESCUE;direc(src); allx=list(src.iterdir())
    if sorted(x.name for x in allx)!=sorted(RESCUE_FILES) or any(x.is_symlink() or not x.is_file() for x in allx): raise Stop("RESCUE_CONTEXT_ALLOWLIST_MISMATCH",69)
    ctx=w/"context";ctx.mkdir(mode=0o700); lines=[]
    for n in RESCUE_FILES:
        rel=str(RESCUE/n)
        if rel not in entries: raise Stop("RESCUE_NOT_IN_MANIFEST:"+rel,69)
        a=src/n;reg(a)
        if sha(a)!=entries[rel]: raise Stop("RESCUE_SOURCE_MISMATCH:"+n,69)
        b=ctx/n
        with a.open("rb") as x,b.open("xb") as y: shutil.copyfileobj(x,y);y.flush();os.fsync(y.fileno())
        os.chmod(b,0o600);reg(b,0,0o600); h=sha(b)
        if h!=entries[rel]: raise Stop("RESCUE_STAGE_MISMATCH:"+n,69)
        lines.append(f"{h}  {n}\n")
    raw="".join(sorted(lines)).encode();atomic(w/"context-manifest.sha256",raw)
    return ctx,hashlib.sha256(raw).hexdigest()

def preflight(r,s):
    e=manifest(r["expected_hash"])
    return result(r,"PASS",0,"CANDIDATE_VERIFIED",verified_files=len(e),artifact_hashes=[{"path":MANIFEST,"sha256":r["expected_hash"]}])

def build(r,s):
    e=manifest(r["expected_hash"]);active(r,s);w=workdir(r)
    ctx,ch=stage(e,w); iid=w/"image.iid"
    x=run([docker(),"build","--pull=false","--file",str(ctx/"Dockerfile"),"--iidfile",str(iid),str(ctx)],180)
    if x.returncode: raise Stop("RESCUE_BUILD_FAILED",x.returncode or 70)
    reg(iid,0,0o600); image=iid.read_text().strip()
    if not re.fullmatch(r"sha256:[0-9a-f]{64}",image): raise Stop("IMAGE_ID_INVALID",70)
    z=run([docker(),"image","inspect",image,"--format","{{.Id}}"])
    if z.returncode or z.stdout.strip()!=image: raise Stop("IMAGE_ID_INSPECT_MISMATCH",70)
    ev={"image_id":image,"candidate_manifest_sha256":r["expected_hash"],"context_manifest_sha256":ch,"iidfile":str(iid),"workdir":str(w),"built_at":now()}
    atomic(w/"evidence.json",(json.dumps(ev,sort_keys=True,separators=(",",":"))+"\n").encode())
    s["images"][r["change_id"]]=ev;clear(s);save(s)
    return result(r,"PASS",0,"RESCUE_IMAGE_BUILT",immutable_image_id=image,context_manifest_sha256=ch)

def image(r,s):
    if s["recovery"]: raise Stop("RECOVERY_REQUIRED",65)
    e=s["images"].get(r["change_id"])
    if not isinstance(e,dict): raise Stop("NO_BOUND_IMAGE",70,"UNVERIFIED")
    if e.get("candidate_manifest_sha256")!=r["expected_hash"]: raise Stop("BOUND_IMAGE_MISMATCH",70)
    i=e.get("image_id")
    if not isinstance(i,str) or not re.fullmatch(r"sha256:[0-9a-f]{64}",i): raise Stop("BOUND_IMAGE_INVALID",70)
    return e

def inspect(r,s):
    manifest(r["expected_hash"]);e=image(r,s);i=e["image_id"]
    x=run([docker(),"image","inspect",i,"--format","{{.Id}} {{json .RepoDigests}}"])
    if x.returncode or not x.stdout.strip().startswith(i+" "): raise Stop("IMAGE_INSPECT_FAILED",70,"UNVERIFIED")
    return result(r,"PASS",0,"IMAGE_INSPECT_VERIFIED",immutable_image_id=i,inspect=x.stdout.strip())

def runargv(i,op):
    return [docker(),"run","--rm","--network","none","--user","1002:1002","--read-only","--cap-drop","ALL","--security-opt","no-new-privileges:true","--cpus","0.50","--memory","128m","--pids-limit","64","--tmpfs","/tmp:size=16m,noexec,nosuid,nodev",i,op]

def testrescue(r,s):
    manifest(r["expected_hash"]);e=image(r,s);i=e["image_id"]; obs=[]
    for op,expect in (("health",0),("unknown_op",64),("start_production",65)):
        x=run(runargv(i,op));obs.append({"operation":op,"expected_exit":expect,"actual_exit":x.returncode})
        if x.returncode!=expect: raise Stop("RESCUE_TEST_MISMATCH:"+op,70)
    return result(r,"PASS",0,"RESCUE_TESTS_VERIFIED",immutable_image_id=i,tests=obs,runtime_hardening="PASS_FOR_TEST_INVOCATION")

def cleanup(r,s):
    manifest(r["expected_hash"]);e=image(r,s);w=Path(e["workdir"]).resolve(strict=True);base=WORK.resolve(strict=True)
    if base not in w.parents: raise Stop("CLEANUP_ESCAPE",70)
    c=w/"context"
    if c.exists():direc(c,0,0o700);shutil.rmtree(c)
    return result(r,"PASS",0,"EPHEMERAL_CONTEXT_REMOVED_EVIDENCE_PRESERVED")

HAND={"candidate_preflight":preflight,"build_rescue":build,"inspect_image":inspect,"run_rescue_test":testrescue,"cleanup_own_temp":cleanup}

def runner_uid():
    x=os.environ.get("ZEUS_RUNNER_UID","")
    if not x.isdigit() or int(x)<1000 or int(x)==65534: raise Stop("RUNNER_UID_INVALID",70)
    return int(x)
def peer(c): return struct.unpack("3i",c.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,struct.calcsize("3i")))[1]

def process(o,s):
    r=validate(o)
    if s["recovery"]: raise Stop("RECOVERY_REQUIRED",65)
    if r["idempotency_key"] in s["seen"]: raise Stop("DUPLICATE_IDEMPOTENCY_KEY",65)
    s["seen"].append(r["idempotency_key"]);s["seen"]=s["seen"][-4096:];save(s)
    return HAND[r["operation"]](r,s)

def conn(c):
    uid=peer(c)
    if uid!=runner_uid():
        audit({"at":now(),"event":"peer_denied","peer_uid":uid});c.sendall(b'{"status":"FAIL","exit_code":77,"reason":"PEER_UID_REJECTED"}\n');return
    c.settimeout(5);b=bytearray()
    while True:
        q=c.recv(4096)
        if not q:break
        b.extend(q)
        if len(b)>MAX:raise Stop("REQUEST_TOO_LARGE",64)
        if b"\n" in q:break
    if b.count(b"\n")!=1 or not b.endswith(b"\n"):raise Stop("FRAMING_INVALID",64)
    try:o=json.loads(b[:-1].decode())
    except Exception:raise Stop("INVALID_JSON",64)
    s=load()
    try:z=process(o,s)
    except Stop as e:z={"operation":o.get("operation") if isinstance(o,dict) else None,"job_id":o.get("job_id") if isinstance(o,dict) else None,"change_id":o.get("change_id") if isinstance(o,dict) else None,"status":e.status,"exit_code":e.code,"reason":e.reason,"finished_at":now()}
    audit({"at":now(),"event":"request_result","peer_uid":uid,"operation":z.get("operation"),"job_id":z.get("job_id"),"change_id":z.get("change_id"),"status":z.get("status"),"exit_code":z.get("exit_code"),"reason":z.get("reason")})
    raw=(json.dumps(z,sort_keys=True,separators=(",",":"))+"\n").encode()
    if len(raw)>MAX:raise Stop("RESPONSE_TOO_LARGE",70)
    c.sendall(raw)

def listen():
    if os.environ.get("LISTEN_PID")!=str(os.getpid()) or os.environ.get("LISTEN_FDS")!="1":raise Stop("SYSTEMD_SOCKET_ACTIVATION_REQUIRED",70)
    return socket.fromfd(3,socket.AF_UNIX,socket.SOCK_STREAM)

def main():
    if os.geteuid()!=0:return 30
    direc(STATE_ROOT,0,0o700)
    if not WORK.exists():WORK.mkdir(mode=0o700)
    direc(WORK,0,0o700);direc(AUDIT.parent,0,0o750);runner_uid();s=listen()
    while True:
        c,_=s.accept()
        with c:
            try:conn(c)
            except Stop as e:
                try:c.sendall((json.dumps({"status":e.status,"exit_code":e.code,"reason":e.reason,"finished_at":now()},separators=(",",":"))+"\n").encode())
                except OSError:pass
            except Exception:
                try:c.sendall(b'{"status":"UNVERIFIED","exit_code":70,"reason":"ADAPTER_INTERNAL_ERROR"}\n')
                except OSError:pass

if __name__=="__main__":raise SystemExit(main())
