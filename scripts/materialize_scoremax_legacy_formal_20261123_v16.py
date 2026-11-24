"""Compose exact V13 with fresh bounded legacy formal-evidence aggregation."""
import importlib.util,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def main():
 build=load('legacy_formal_build_v16',ROOT/'ux_vnext_overlay/biology_receiver_20261027/legacy_formal_build_20261123_v16.py')
 runtime=ROOT/'scoremax_runtime_v669b'
 if runtime.exists() and build.tree(runtime)==build.AFTER_TREE:return build.apply(runtime)
 prior=load('accepted_programme_v13',ROOT/'scripts/materialize_scoremax_programme_display_20261123_v13.py');prior.main()
 return build.apply(runtime)
if __name__=='__main__':print(json.dumps(main(),sort_keys=True))
