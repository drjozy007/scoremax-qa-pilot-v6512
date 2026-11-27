"""Exact-parent build-only native numeric recovery; opens no database."""
from pathlib import Path
import hashlib,json,os,sys
HERE=Path(__file__).resolve().parent
def sha(raw):return hashlib.sha256(raw).hexdigest()
def tree(root):return sha(json.dumps({p.relative_to(root).as_posix():sha(p.read_bytes())for p in root.rglob('*')if p.is_file()and'__pycache__'not in p.parts and p.suffix!='.pyc'},sort_keys=True,separators=(',',':')).encode())
def apply(root,*,build_mode=False):
 root=Path(root).absolute()
 if not build_mode:raise RuntimeError('EXPLICIT_BUILD_MODE_REQUIRED')
 if any(p.is_symlink()for p in(root,*root.parents))or not root.is_dir():raise ValueError('PHYSICAL_BUILD_ROOT_REQUIRED')
 root=root.resolve()
 if root==Path('/data')or Path('/data')in root.parents:raise ValueError('PRODUCTION_DATA_PATH_FORBIDDEN')
 m=json.loads((HERE/'manifest.json').read_text())
 if m['lane']=='runtime':
  sys.path.insert(0,str(root));from backup_lifecycle_v1 import runtime_source_identity
  identity=runtime_source_identity
 else:identity=tree
 observed=identity(root)
 if observed==m['candidate_source_closure']:return {'status':'PASSED','replayed':True,'source_closure':observed,'database_opened':False}
 if observed!=m['parent_source_closure']:raise ValueError('EXACT_ACCEPTED_NUMERICAL_PARENT_REQUIRED')
 prepared={}
 for name,pins in m['files'].items():
  if Path(name).name!=name:raise ValueError('FLAT_RUNTIME_PATH_REQUIRED')
  source=HERE/'runtime'/name;dest=root/name
  if dest.is_symlink():raise ValueError('LINKED_RUNTIME_FILE_FORBIDDEN')
  raw=source.read_bytes()
  if sha(raw)!=pins['after_sha256']:raise ValueError('FROZEN_NUMERICAL_SOURCE_DRIFT')
  if pins['before_sha256']is None:
   if dest.exists():raise ValueError('NEW_NUMERICAL_PATH_ALREADY_EXISTS')
  elif not dest.is_file()or sha(dest.read_bytes())!=pins['before_sha256']:raise ValueError('NUMERICAL_PARENT_BYTES_DRIFT')
  compile(raw,str(dest),'exec');prepared[dest]=raw
 for dest,raw in prepared.items():dest.write_bytes(raw)
 observed=identity(root)
 if observed!=m['candidate_source_closure']:raise ValueError('NUMERICAL_CLOSURE_RESULT_INVALID')
 return {'status':'PASSED','replayed':False,'source_closure':observed,'database_opened':False,'schema_changed':False}
if __name__=='__main__':print(json.dumps(apply(sys.argv[1],build_mode=True),sort_keys=True))
