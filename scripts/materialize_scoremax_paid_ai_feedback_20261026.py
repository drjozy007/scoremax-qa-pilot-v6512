"""Reuse the exact public runtime; consolidate written-response interpretation, disabled by default."""
import hashlib,importlib.util,json
from pathlib import Path
REPO=Path(__file__).resolve().parents[1]
EXPECTED='ec1a17eb734df0657147f76800034807c53b9c31fa0236d0c56854827b7560a4'
def digest(root):
    m={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
    return len(m),hashlib.sha256(json.dumps(m,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def load(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def materialize():
    root=REPO/'scoremax_runtime_v669b'
    if root.exists():
        assert digest(root)==(263,EXPECTED),'EXISTING_CONSOLIDATED_WRITTEN_RUNTIME_MISMATCH'
        return {'replayed':True,'runtime_sha256':EXPECTED,'files':263}
    load('accepted_public_builder',REPO/'scripts/materialize_scoremax_public_opening_20261026.py').materialize()
    load('paid_feedback_delta',REPO/'ux_vnext_overlay/ux_paid_ai_marking_20261026.py').apply(root)
    assert digest(root)==(263,EXPECTED),'PAID_AI_RUNTIME_MISMATCH'
    return {'replayed':False,'runtime_sha256':EXPECTED,'files':263,'provider_calls':0,'default_AI_budget':0,'historical_tests_run':0}
if __name__=='__main__':print('SCOREMAX_PAID_AI_RUNTIME='+json.dumps(materialize(),sort_keys=True))
