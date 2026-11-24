"""Compose accepted V9 navigation and the exact native qualification correction."""
import importlib.util,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def main():
 build=load('successor_build_v10',ROOT/'ux_vnext_overlay/biology_receiver_20261027/successor_qualification_build_20261123_v10.py')
 runtime=ROOT/'scoremax_runtime_v669b'
 if runtime.exists() and build.tree(runtime)==build.AFTER_TREE:return build.apply(runtime)
 prior=load('accepted_navigation_v9',ROOT/'scripts/materialize_scoremax_sqlite_nav_candidate_20261116.py');prior.main()
 return build.apply(runtime)
if __name__=='__main__':print(json.dumps(main(),sort_keys=True))
