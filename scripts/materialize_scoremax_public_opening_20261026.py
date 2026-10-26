"""Reuse the accepted build and apply only bounded public onboarding."""
import hashlib,importlib.util,json
from pathlib import Path
REPO=Path(__file__).resolve().parents[1]
EXPECTED='bed7d678f3c43d10d85ab31c699ad78994e0764670890c2fd0c4c77c2629f69c'
def digest(root):
    m={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
    return len(m),hashlib.sha256(json.dumps(m,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def materialize():
    root=REPO/'scoremax_runtime_v669b'
    if root.exists():
        assert digest(root)==(261,EXPECTED),'EXISTING_PUBLIC_RUNTIME_MISMATCH'
        return {'replayed':True,'runtime_sha256':EXPECTED,'files':261}
    load('accepted_display_builder',REPO/'scripts/materialize_scoremax_learner_display_20261026.py').materialize()
    load('public_onboarding_delta',REPO/'ux_vnext_overlay/ux_public_student_opening_20261026.py').apply(root)
    assert digest(root)==(261,EXPECTED),'PUBLIC_RUNTIME_MISMATCH'
    return {'replayed':False,'runtime_sha256':EXPECTED,'files':261,'historical_tests_run':0,'question_imports':0}
if __name__=='__main__':print('SCOREMAX_PUBLIC_RUNTIME='+json.dumps(materialize(),sort_keys=True))
