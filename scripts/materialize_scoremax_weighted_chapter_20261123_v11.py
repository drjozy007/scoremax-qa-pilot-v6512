"""Compose exact V10 qualification with bounded native chapter-count aggregation."""
import importlib.util,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def main():
 build=load('weighted_chapter_build_v11',ROOT/'ux_vnext_overlay/biology_receiver_20261027/weighted_chapter_build_20261123_v11.py')
 runtime=ROOT/'scoremax_runtime_v669b'
 if runtime.exists() and build.tree(runtime)==build.AFTER_TREE:return build.apply(runtime)
 prior=load('accepted_successor_v10',ROOT/'scripts/materialize_scoremax_successor_qualification_20261123_v10.py');prior.main()
 return build.apply(runtime)
if __name__=='__main__':print(json.dumps(main(),sort_keys=True))
