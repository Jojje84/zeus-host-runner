#!/usr/bin/env python3
import importlib.util, pathlib
p=pathlib.Path(__file__).with_name("zeus_host_adapter.py")
t=p.read_text()
assert "shell=True" not in t
assert "os.system(" not in t
assert "SO_PEERCRED" in t
assert "SYSTEMD_SOCKET_ACTIVATION_REQUIRED" in t
assert "arbitrary_command" not in t
s=importlib.util.spec_from_file_location("m",p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
x={"operation":"candidate_preflight","change_id":"V31-TEST-12345678","candidate_root":str(m.ROOT),"expected_hash":"a"*64,"job_id":"job","nonce":"abcdefghijklmnop","expires_at":"2099-01-01T00:00:00Z","requested_by":"zeus-production","idempotency_key":"idempotency-key-0001"}
assert m.validate(x)["operation"]=="candidate_preflight"
y=dict(x);y["operation"]="arbitrary_command"
try:m.validate(y);raise AssertionError("unknown op accepted")
except m.Stop as e:assert e.code==64
orig=m.docker;m.docker=lambda:"/usr/bin/docker"
try:
 a=" ".join(m.runargv("sha256:"+"b"*64,"health"))
 for q in ("--network none","--read-only","--cap-drop ALL","--security-opt no-new-privileges:true","--pids-limit 64"):assert q in a
finally:m.docker=orig
print("STATIC_AND_PURE_TESTS=PASS")
