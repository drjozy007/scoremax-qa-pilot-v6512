"""Accepted receiver then exact terminal-numeric-rejection correction."""
from pathlib import Path
import importlib.util,json
ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def main():
 patch=load('numeric_rejection_recovery',ROOT/'numeric_rejection_recovery_20261127_v3/apply.py')
 runtime=ROOT/'scoremax_runtime_v669b'
 if runtime.is_dir():
  manifest=json.loads((ROOT/'numeric_rejection_recovery_20261127_v3/manifest.json').read_text())
  if patch.tree(runtime)==manifest['candidate_source_closure']:return patch.apply(runtime,build_mode=True)
 prior=load('accepted_receiver_20261126',ROOT/'scripts/materialize_scoremax_practice_label_20261124_v17_receiver_accepted_20261126.py');prior.main()
 return patch.apply(runtime,build_mode=True)
if __name__=='__main__':print(json.dumps(main(),sort_keys=True))
