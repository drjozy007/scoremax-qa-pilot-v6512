"""Exact accepted native guard after fail-closed cutover access; no bypass."""
from pathlib import Path
import hashlib,importlib.util,runpy
p=Path(__file__).resolve().parent
target=p/'scoremax_persistent_storage_guard_native_accepted_20261127.py'
assert hashlib.sha256(target.read_bytes()).hexdigest()=='7f307f6bb743d4830e34f5df20ad56c1704ee3d8c37f48b131108f95400f8d6f','ACCEPTED_NATIVE_GUARD_BYTES_DRIFT'
spec=importlib.util.spec_from_file_location('cutover_storage_access',p.parent/'consolidated_receiver_20261127_v1/startup_storage_access.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.wait_for_native_capacity()
runpy.run_path(str(target),run_name='__main__')
