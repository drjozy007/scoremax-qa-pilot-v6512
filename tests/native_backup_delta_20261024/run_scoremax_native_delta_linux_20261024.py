"""Reconstruct accepted source-only fixtures; run only new tiny delta cases."""
import base64
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

REPO = Path.cwd().resolve()
PAYLOAD = REPO/'qualification/native_backup_delta_20261024'
TESTS = REPO/'tests/native_backup_delta_20261024'
OUT = REPO/'native-backup-evidence'
OUT.mkdir(exist_ok=True)
WORK = Path(tempfile.mkdtemp(prefix='native_backup_delta_',dir=os.environ['RUNNER_TEMP'])).resolve()
HERE = WORK/'delta'
HERE.mkdir()
CAPTURE = WORK/'scoremax_exact_runtime'
CAPTURE.mkdir()
raw = (TESTS/'accepted630_source_capture.json.gz').read_bytes()
assert hashlib.sha256(raw).hexdigest() == '9e6d5f7925ba86caeef661b56cd126df02f0b16298e0070537ee21b31a8234e5'
saved = json.loads(gzip.decompress(raw))
assert saved['file_count'] == 259 and saved['source_commit'] == '6302547c0543057c249b60b65e3348a52d9f6a27'
manifest = json.loads((PAYLOAD/'runtime_capture_manifest_630.json').read_text())
assert set(saved['files']) == set(manifest)
assert hashlib.sha256(json.dumps(manifest,sort_keys=True,separators=(',',':')).encode()).hexdigest() == '28aeb812a0ed269840ff73ea45f6864cf78138e57f98ab6c1c69093161ba6279'
for name, encoded in saved['files'].items():
    rel = Path(name)
    assert not rel.is_absolute() and '..' not in rel.parts and not any(p.startswith('.') for p in rel.parts)
    assert rel.suffix.lower() not in {'.db','.sqlite','.sqlite3','.key','.pem','.env'}
    data = base64.b64decode(encoded,validate=True)
    assert hashlib.sha256(data).hexdigest() == manifest[name]
    target = CAPTURE/rel
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(data)
for name in ('app.py','pilot_readiness_engine.py','backup_capacity_v1.py','runtime_capture_manifest_630.json'):
    shutil.copyfile(PAYLOAD/name,HERE/name)
for name in ('app.py','pilot_readiness_engine.py'):
    shutil.copyfile(CAPTURE/name,HERE/name.replace('.py','.baseline.py'))
for name in ('test_native_backup_delta_20261024.py','check_native_backup_sources_20261024.py',
             'deploy_ux_vnext.accepted630.source.py','deploy_ux_vnext_native_backup_hook.patch'):
    shutil.copyfile(TESTS/name,HERE/name)
shutil.copyfile(REPO/'scripts/apply_scoremax_native_backup_delta_20261024.py',HERE/'apply_scoremax_native_backup_delta_20261024.py')
codes = []
for name in ('check_native_backup_sources_20261024.py','test_native_backup_delta_20261024.py'):
    p = subprocess.run([sys.executable,'-B',str(HERE/name)],cwd=HERE,timeout=120,text=True,capture_output=True)
    codes.append(p.returncode)
    (OUT/(name+'.log')).write_text(p.stdout+p.stderr)
    print(p.stdout,flush=True)
    print(p.stderr,flush=True)
for name in ('NATIVE_BACKUP_SOURCE_CHECK_RESULT_20261024.json','NATIVE_BACKUP_DELTA_TEST_RESULT_20261024.json'):
    assert (HERE/name).is_file(), name
    shutil.copyfile(HERE/name,OUT/name)
    result = json.loads((HERE/name).read_text())
    assert result['passed'], name
assert codes == [0,0], codes
print('New native source and tiny synthetic Linux cases passed; services/imports/historical replay0',flush=True)
