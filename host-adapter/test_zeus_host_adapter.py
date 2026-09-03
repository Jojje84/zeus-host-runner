import importlib.util
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE=Path(__file__).resolve().parent
SPEC=importlib.util.spec_from_file_location('zha',HERE/'zeus_host_adapter.py')
zha=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(zha)

class FakeCfg:
    def __init__(self,root):
        self.socket_path=root/'run'/'adapter.sock'; self.state_dir=root/'state'; self.audit_path=self.state_dir/'audit'/'host-adapter.jsonl'; self.state_path=self.state_dir/'state.json'; self.runs_dir=self.state_dir/'runs'
        self.allowed_uid=1003; self.allowed_gid=1003; self.rescue_uid=1002; self.rescue_gid=1002; self.candidate_root=root/'candidate'; self.docker='/usr/bin/docker'; self.max_runs_per_change=6

class FakeRun:
    def __init__(self): self.calls=[]; self.image_id='sha256:'+'a'*64
    def __call__(self,argv,**kwargs):
        self.calls.append(list(argv))
        class CP: pass
        cp=CP(); cp.returncode=0; cp.stderr=''
        if 'build' in argv:
            Path(argv[argv.index('--iidfile')+1]).write_text(self.image_id+'\n'); cp.stdout='built\n'
        elif 'inspect' in argv and '--format' in argv:
            fmt=argv[argv.index('--format')+1]; cp.stdout=self.image_id+(' []\n' if 'RepoDigests' in fmt else '\n')
        elif 'run' in argv:
            op=argv[-1]; cp.returncode={'health':0,'unknown_op':64,'start_production':65}[op]; cp.stdout=op+'\n'
        else: cp.stdout=''
        return cp

def request(root,op='candidate_preflight',suffix='1'):
    manifest=root/'candidate'/'ARTIFACT-HASHES.sha256'
    return {'operation':op,'change_id':'V31-TEST-20260903','candidate_root':str(root/'candidate'),'expected_hash':zha.sha256_file(manifest),'job_id':'job-'+suffix,'nonce':'nonce-abcdefghijklmnop'+suffix,'expires_at':(datetime.now(timezone.utc)+timedelta(minutes=10)).isoformat().replace('+00:00','Z'),'requested_by':'zeus-production','idempotency_key':'idem-abcdefghijklmnop'+suffix}

class Tests(unittest.TestCase):
    def setUp(self):
        self.td=tempfile.TemporaryDirectory(); self.root=Path(self.td.name); self.cfg=FakeCfg(self.root)
        ctx=self.cfg.candidate_root/'zeus-rescue'/'build-context'; ctx.mkdir(parents=True)
        files=[]
        for name in ['BUILD-METADATA.json','Dockerfile','operations.allowlist','rescue-controller.js']:
            f=ctx/name; f.write_text(name+'\n'); files.append(f)
        sentinel=self.cfg.candidate_root/'sentinel.txt'; sentinel.write_text('locked\n'); files.append(sentinel)
        lines=[]
        for f in files:
            rel=f.relative_to(self.cfg.candidate_root).as_posix(); lines.append(f'{zha.sha256_file(f)}  {rel}')
        (self.cfg.candidate_root/'ARTIFACT-HASHES.sha256').write_text('\n'.join(lines)+'\n')
        self.fake=FakeRun(); self.state=zha.StateStore(self.cfg); self.adapter=zha.HostAdapter(self.cfg,self.state,runner=self.fake)
    def tearDown(self): self.td.cleanup()
    def test_preflight_pass(self): self.assertEqual(self.adapter.execute(request(self.root))['status'],'PASS')
    def test_unknown_field_fails(self):
        q=request(self.root); q['extra']='x'
        with self.assertRaises(zha.FailClosed): self.adapter.execute(q)
    def test_wrong_candidate_fails(self):
        q=request(self.root); q['candidate_root']='/tmp/nope'
        with self.assertRaises(zha.FailClosed): self.adapter.execute(q)
    def test_manifest_bound_file_tamper_fails(self):
        q=request(self.root); (self.cfg.candidate_root/'sentinel.txt').write_text('tampered\n')
        with self.assertRaises(zha.FailClosed) as cm: self.adapter.execute(q)
        self.assertEqual(cm.exception.reason,'CANDIDATE_FILE_HASH_MISMATCH')
    def test_rescue_context_must_be_manifest_bound(self):
        manifest=self.cfg.candidate_root/'ARTIFACT-HASHES.sha256'
        lines=[x for x in manifest.read_text().splitlines() if not x.endswith('  zeus-rescue/build-context/Dockerfile')]
        manifest.write_text('\n'.join(lines)+'\n')
        q=request(self.root,'build_rescue','8')
        with self.assertRaises(zha.FailClosed) as cm: self.adapter.execute(q)
        self.assertEqual(cm.exception.reason,'RESCUE_CONTEXT_NOT_MANIFEST_BOUND')
    def test_build_binds_exact_iid(self):
        r=self.adapter.execute(request(self.root,'build_rescue','2')); self.assertEqual(r['immutable_image_id'],self.fake.image_id); self.assertEqual(self.state.state['last_image_id'],self.fake.image_id)
    def test_duplicate_denied(self):
        q=request(self.root,suffix='3'); self.adapter.execute(q)
        with self.assertRaises(zha.FailClosed): self.adapter.execute(q)
    def test_rescue_suite_expected_exits(self):
        self.adapter.execute(request(self.root,'build_rescue','4')); r=self.adapter.execute(request(self.root,'run_rescue_test','5')); self.assertEqual(r['status'],'PASS'); self.assertEqual([x['actual_exit'] for x in r['tests']],[0,64,65])
    def test_build_failure_enters_recovery(self):
        class Bad(FakeRun):
            def __call__(self,argv,**kwargs):
                cp=super().__call__(argv,**kwargs)
                if 'build' in argv: cp.returncode=1
                return cp
        state=zha.StateStore(self.cfg); a=zha.HostAdapter(self.cfg,state,runner=Bad())
        with self.assertRaises(zha.FailClosed): a.execute(request(self.root,'build_rescue','6'))
        self.assertTrue(state.state['recovery_required'])
    def test_cleanup_cannot_escape_runs(self): self.assertEqual(self.adapter.execute(request(self.root,'cleanup_own_temp','7'))['status'],'PASS')

if __name__=='__main__': unittest.main(verbosity=2)
