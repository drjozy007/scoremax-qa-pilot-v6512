"""Materialize the already captured live source and admitted small launch deltas.
No app execution, database, credentials, question payload export or old qualification.
The original deploy_ux_vnext.py and every historical check remain unchanged.
"""
import base64,gzip,hashlib,importlib.util,json,os
from pathlib import Path
REPO=Path(__file__).resolve().parents[1]
CAPTURE=REPO/'tests/native_backup_delta_20261024/accepted630_source_capture.json.gz'
BASE='28aeb812a0ed269840ff73ea45f6864cf78138e57f98ab6c1c69093161ba6279'
EXPECTED='6151aa9c27feea18b36080613350b97230278eac8793f447d4db7e66486e87fe'
def digest(data):return hashlib.sha256(data).hexdigest()
def tree(m):return digest(json.dumps(m,sort_keys=True,separators=(',',':')).encode())
def module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def materialize():
 raw=CAPTURE.read_bytes();assert digest(raw)=='9e6d5f7925ba86caeef661b56cd126df02f0b16298e0070537ee21b31a8234e5'
 saved=json.loads(gzip.decompress(raw));manifest=json.loads((REPO/'qualification/native_backup_delta_20261024/runtime_capture_manifest_630.json').read_text())
 assert saved['source_commit']=='6302547c0543057c249b60b65e3348a52d9f6a27' and len(manifest)==259 and set(saved['files'])==set(manifest) and tree(manifest)==BASE
 payload={}
 for name,encoded in saved['files'].items():
  p=Path(name);assert not p.is_absolute() and '..' not in p.parts and not any(x.startswith('.') for x in p.parts) and p.suffix.lower() not in {'.db','.sqlite','.sqlite3','.env','.key','.pem'}
  data=base64.b64decode(encoded,validate=True);assert digest(data)==manifest[name];payload[name]=data
 root=REPO/'scoremax_runtime_v669b'
 guard=REPO/'scripts/scoremax_persistent_storage_guard.py'
 assert digest(guard.read_bytes()) in {'1418af71119b5a0a3517149aac847ed47c373433ac60c2d1adc5cba855583b86','c1bff2fcbe000a05aeab4401b9267dd1e460425c485aa6efc683c642fed47195'},'STARTUP_GUARD_BASE_MISMATCH'
 assert Path.cwd().resolve()==REPO,'SOURCE_BUILD_CWD_MISMATCH'
 module('existing_postrelease_guard_overlay',REPO/'ux_vnext_overlay/ux_persistent_guard_postrelease_state.py').apply_persistent_guard_postrelease_state(root)
 module('existing_batch_retirement_overlay',REPO/'ux_vnext_overlay/ux_persistent_guard_batch_retirement.py').apply_persistent_guard_batch_retirement(root)
 guard.write_bytes(guard.read_text(encoding='utf8').encode())
 assert digest(guard.read_bytes())=='c1bff2fcbe000a05aeab4401b9267dd1e460425c485aa6efc683c642fed47195','STARTUP_GUARD_DERIVED_MISMATCH'
 if root.exists():
  assert root.is_dir() and not root.is_symlink()
  current={p.relative_to(root).as_posix():digest(p.read_bytes()) for p in root.rglob('*') if p.is_file()}
  assert len(current)==261 and tree(current)==EXPECTED,'EXISTING_RUNTIME_NOT_EXACT_LAUNCH_CANDIDATE'
  return {'replayed':True,'runtime_sha256':EXPECTED,'files':261}
 root.mkdir()
 for name,data in payload.items():
  p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
 accepted=module('accepted_native_backup_installer',REPO/'scripts/apply_scoremax_native_backup_delta_20261024.py').apply(root)
 assert accepted['derived_tree_sha256']=='e18573635e90ad3149bafd4ece5b74ea68e0a6d48e29e2222e71400fbd9d7b3c'
 module('launch_invitation_installer',REPO/'ux_vnext_overlay/ux_invite_only_pilot.py').apply(root)
 current={p.relative_to(root).as_posix():digest(p.read_bytes()) for p in root.rglob('*') if p.is_file()}
 assert len(current)==261 and tree(current)==EXPECTED,'FINAL_RUNTIME_SOURCE_MISMATCH'
 return {'replayed':False,'runtime_sha256':EXPECTED,'files':261,'startup_guard_sha256':'c1bff2fcbe000a05aeab4401b9267dd1e460425c485aa6efc683c642fed47195','base_live_commit':saved['source_commit'],'historical_qualifications_run':0,'app_imports':0,'database_access':False}
if __name__=='__main__':print('SCOREMAX_LAUNCH_RUNTIME='+json.dumps(materialize(),sort_keys=True))
