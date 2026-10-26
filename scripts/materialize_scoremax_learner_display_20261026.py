"""Reuse the accepted launch build; add only the owner-requested learner-display delta."""
import hashlib,importlib.util,json
from pathlib import Path
REPO=Path(__file__).resolve().parents[1]
EXPECTED='037ee7cf7e2cf4a4400c28104a7a884b6cccfa4669c6a2ec85ee2f57858779ba'
def digest(root):
 m={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
 return len(m),hashlib.sha256(json.dumps(m,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def load(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def materialize():
 root=REPO/'scoremax_runtime_v669b'
 if root.exists():
  assert digest(root)==(261,EXPECTED),'EXISTING_DISPLAY_RUNTIME_MISMATCH'
  return {'replayed':True,'files':261,'runtime_sha256':EXPECTED}
 load('existing_launch_materializer',REPO/'scripts/materialize_scoremax_accepted630_launch_20261025.py').materialize()
 load('learner_display_delta',REPO/'ux_vnext_overlay/ux_learner_display_20261026.py').apply(root)
 assert digest(root)==(261,EXPECTED),'DISPLAY_RUNTIME_MISMATCH'
 return {'replayed':False,'files':261,'runtime_sha256':EXPECTED,'question_marking_or_release_mutations':0,'historical_tests_run':0}
if __name__=='__main__':print('SCOREMAX_DISPLAY_RUNTIME='+json.dumps(materialize(),sort_keys=True))
