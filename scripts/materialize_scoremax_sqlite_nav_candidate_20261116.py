"""Compose the current pending/scored receiver with exact SQLite navigation delta.

No database is opened and no indexes are created by this materializer.
"""
import importlib.util,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def main():
 build=load('current_navigation',ROOT/'ux_vnext_overlay/biology_receiver_20261027/sqlite_navigation_build_20261123_v1.py')
 runtime=ROOT/'scoremax_runtime_v669b'
 if runtime.exists() and build.tree(runtime)==build.AFTER_TREE:return build.apply(runtime)
 prior=load('current_receiver',ROOT/'scripts/materialize_scoremax_scored_saq_20261122.py')
 prior.materialize()
 return build.apply(runtime)
if __name__=='__main__':print(json.dumps(main(),sort_keys=True))
