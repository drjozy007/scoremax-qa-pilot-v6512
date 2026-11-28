"""Exact executive receiver overlay after the accepted consolidated V3 parent."""
from pathlib import Path
import hashlib,sys,zipfile,subprocess,os
root=Path(__file__).resolve().parents[1]
archive=root/'engineering/executive_full_inventory_20261128_v1/SM_Executive_Full_Inventory_20261128_V1.zip'
assert hashlib.sha256(archive.read_bytes()).hexdigest()=='fcdb118dd834dd2640327266d497f34b028c15844d038d3dd0135a9f73c5715d','EXECUTIVE_RECEIVER_ARCHIVE_DRIFT'
with zipfile.ZipFile(archive)as z:
 for n in z.namelist():assert not Path(n).is_absolute()and'..'not in Path(n).parts
 z.extractall(root/'engineering/executive_full_inventory_20261128_v1')
candidate=root/'engineering/executive_full_inventory_20261128_v1/candidate'
subprocess.run([sys.executable,'-B',str(candidate/'verify_candidate.py')],check=True)
runtime=root/'scoremax_runtime_v669b'
def tree(p):return hashlib.sha256(__import__('json').dumps({f.relative_to(p).as_posix():hashlib.sha256(f.read_bytes()).hexdigest()for f in p.rglob('*')if f.is_file()and'__pycache__'not in f.parts and f.suffix!='.pyc'},sort_keys=True,separators=(',',':')).encode()).hexdigest()
if tree(runtime)not in {'2f4712a2ad3cf75b98f5d1a05217d76c8c9c18c757ba0bca95b6a74a1e3b9fd4','87775d8eb125a27283f736635557fffcd74f1afc169a280a9c0f4fe08d4858c0'}:
 subprocess.run([sys.executable,'-B',str(root/'scripts/materialize_consolidated_receiver_20261128_v3_parent.py')],check=True)
subprocess.run([sys.executable,'-B',str(candidate/'build_overlay.py'),'--system','scoremax','--runtime',str(runtime)],env=dict(os.environ,PH_GROUPED_RECOVERY_BUILD='1'),check=True)
