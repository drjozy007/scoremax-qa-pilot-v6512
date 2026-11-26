"""Exact accepted V17 followed by the bounded typed receiver continuation."""
import importlib.util,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
def main():
 patch=load('native_receiver_recovery',ROOT/'native_receiver_recovery_20261126_v1/apply.py')
 runtime=ROOT/'scoremax_runtime_v669b'
 if runtime.exists():
  if any(p.is_symlink() for p in (runtime,*runtime.parents)) or Path('/data') in runtime.resolve().parents or runtime.resolve()==Path('/data'):raise ValueError('RECEIVER_PHYSICAL_BUILD_ROOT_REQUIRED')
  observed=patch.tree(runtime)
  if observed==patch.AFTER:return patch.apply(runtime,build_mode=True)
  if observed not in (patch.BASE,'5746e20cbf82bf01655289c6f97f82863a8ff72cb1bc011d90e2fa39cc12083d'):raise ValueError('RECEIVER_BUILD_UNEXPECTED_RUNTIME_REJECTED')
 prior=load('accepted_practice_label_v17',ROOT/'scripts/materialize_scoremax_practice_label_20261124_v17_accepted.py');prior.main()
 return patch.apply(runtime,build_mode=True)
if __name__=='__main__':print(json.dumps(main(),sort_keys=True))
