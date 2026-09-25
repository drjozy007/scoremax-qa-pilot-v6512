"""Build the canonical runtime twice with distinct hash seeds; compare every source byte.

No deployed service or database is used. Run from the repository, never a live runtime.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT/'scoremax_runtime_v669b'


def manifest() -> dict[str, str]:
    result = {}
    for path in sorted(RUNTIME.rglob('*')):
        if '__pycache__' in path.parts or path.suffix == '.pyc':
            continue
        if path.is_symlink():
            raise RuntimeError('BUILD_SOURCE_SYMLINK_NOT_ALLOWED')
        if path.is_file():
            if path.suffix in {'.db', '.sqlite', '.sqlite3'}:
                raise RuntimeError('BUILD_SOURCE_UNEXPECTED_DATABASE')
            result[path.relative_to(RUNTIME).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    if not result or 'app.py' not in result or 'scoremax_production.py' not in result:
        raise RuntimeError('BUILD_SOURCE_INCOMPLETE')
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', default='build_determinism_results.json')
    args = parser.parse_args()
    if not (ROOT/'deploy_ux_vnext.py').is_file():
        raise RuntimeError('CANONICAL_BUILD_ENTRYPOINT_MISSING')
    reports = []
    for seed in ('17', '839'):
        env = {k:v for k,v in os.environ.items() if not k.startswith(('SCOREMAX_', 'POWER_HOUSE_', 'GROWTH_ENGINE_'))}
        env['PYTHONHASHSEED'] = seed
        wrapper = """import socket,runpy

def deny(*args, **kwargs):
    raise RuntimeError('BUILD_QUALIFICATION_NETWORK_DISABLED')
socket.socket.connect=deny
socket.socket.connect_ex=deny
runpy.run_path('deploy_ux_vnext.py',run_name='__main__')
"""
        with tempfile.TemporaryFile(mode='w+b') as output:
            proc = subprocess.run([sys.executable, '-c', wrapper], cwd=ROOT, env=env, stdout=output, stderr=subprocess.STDOUT, timeout=120)
            if proc.returncode:
                output.seek(0)
                print(output.read().decode('utf-8', errors='replace')[-6000:], file=sys.stderr)
                raise RuntimeError('CANONICAL_BUILD_REPEAT_FAILED')
        files = manifest()
        tree_hash = hashlib.sha256(json.dumps(files, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        reports.append({'hash_seed':seed,'files':files,'tree_sha256':tree_hash})
    left, right = reports
    differences = sorted(p for p in left['files'].keys() | right['files'].keys() if left['files'].get(p) != right['files'].get(p))
    result = {'suite':'CANONICAL_BUILD_DETERMINISM_V1','passed':not differences,'files_compared':len(right['files']),
              'differences':differences,'builds':reports,'network_disabled':True,'deployment_triggered':False}
    Path(args.report).write_text(json.dumps(result, indent=2)+'\n')
    print('SCOREMAX_BUILD_DETERMINISM='+json.dumps({k:v for k,v in result.items() if k!='builds'},sort_keys=True))
    return 1 if differences else 0


if __name__ == '__main__':
    raise SystemExit(main())
