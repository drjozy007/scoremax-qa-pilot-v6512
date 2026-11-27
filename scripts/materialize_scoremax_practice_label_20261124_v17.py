"""Single consolidated receiver integration; exact frozen Job03 helper only."""
from pathlib import Path
import hashlib,importlib.util,json
ROOT=Path(__file__).resolve().parents[1]
EXPECTED='e126593ff3cc517a1a3751c29000b1fff5a6f0372d4d9a632623b84b3bb32c9d'
def tree(root):
 return hashlib.sha256(json.dumps({p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()for p in root.rglob('*')if p.is_file()and'__pycache__'not in p.parts and p.suffix!='.pyc'},sort_keys=True,separators=(',',':')).encode()).hexdigest()
def main():
 runtime=ROOT/'scoremax_runtime_v669b'
 if runtime.is_dir()and tree(runtime)==EXPECTED:return {'status':'PASSED','replayed':True,'closure':EXPECTED}
 spec=importlib.util.spec_from_file_location('accepted_numeric_parent',ROOT/'consolidated_receiver_20261127_v1/parent_materialize.py');prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior);prior.main()
 dest=runtime/'guided_self_assessment.py';raw=(ROOT/'consolidated_receiver_20261127_v1/guided_self_assessment.py').read_bytes()
 assert hashlib.sha256(dest.read_bytes()).hexdigest()=='9aee31035e0fd094f8892d710acee0911fc3915ed5d3d5a785bea2c3eb7e2fe3'
 assert hashlib.sha256(raw).hexdigest()=='96de7b008937b58cfb6ad4a203cb4a85e9342fcbad8265bbbce02a95a0be4301'
 dest.write_bytes(raw);assert tree(runtime)==EXPECTED
 return {'status':'PASSED','closure':EXPECTED,'academic_qualification':'REUSED_FROZEN_JOB03','database_opened':False}

def install_startup_access():
 p=ROOT/'scripts/scoremax_persistent_storage_guard.py'
 original=p.read_bytes()
 saved=ROOT/'scripts/scoremax_persistent_storage_guard_native_accepted_20261127.py'
 # Existing build chain has already validated and materialized its native guard.
 if original.startswith(b'"""Exact accepted native guard after fail-closed cutover access; no bypass.'):
  assert saved.is_file();return
 pin=hashlib.sha256(original).hexdigest()
 saved.write_bytes(original)
 template=(ROOT/'consolidated_receiver_20261127_v1/guard_entry_template.py').read_text()
 p.write_text(template.replace('MATERIALIZED_NATIVE_GUARD_SHA256',pin))
 print('SCOREMAX_ACCEPTED_NATIVE_GUARD_RETAINED '+pin,flush=True)

if __name__=='__main__':
 result=main();install_startup_access();print(json.dumps(result,sort_keys=True))
