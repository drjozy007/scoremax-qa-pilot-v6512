"""Compose accepted V16 and a byte-pinned neutral practice label correction."""
import importlib.util,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def main():
 build=load('practice_label_build_v17',ROOT/'ux_vnext_overlay/biology_receiver_20261027/practice_label_build_20261124_v17.py')
 runtime=ROOT/'scoremax_runtime_v669b'
 if runtime.exists() and build.tree(runtime)==build.AFTER_TREE:return build.apply(runtime)
 prior=load('accepted_legacy_v16',ROOT/'scripts/materialize_scoremax_legacy_formal_20261123_v16.py');prior.main()
 return build.apply(runtime)
if __name__=='__main__':print(json.dumps(main(),sort_keys=True))
