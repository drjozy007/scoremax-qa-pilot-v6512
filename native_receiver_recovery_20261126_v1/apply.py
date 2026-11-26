"""Build-only exact-parent receiver successor; never opens a database."""
from pathlib import Path,PurePosixPath
import hashlib,json,os,tempfile
HERE=Path(__file__).resolve().parent
BASE='daf1071772cca3a5f23f5df7c89707e08a1b9399b3ad1d100ac23ec7b5e2deba'
AFTER='98c60c20e6b1aa9b848f5b01d220cc20f7a8e8a7e16c734b823856fd6ab9694f'
ALLOWED={'app.py','scoremax_integration_v1.py','ph_practice_contracts.py','ph_typed_cloze_contracts_v2.py','receiver_scoped_activation_v1.py','native_activation_policy_20261126_v1.json'}
def sha(raw):return hashlib.sha256(raw).hexdigest()
def tree(root):return sha(json.dumps({p.relative_to(root).as_posix():sha(p.read_bytes()) for p in Path(root).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'},sort_keys=True,separators=(',',':')).encode())
def apply(root, *, build_mode=False):
 root=Path(root)
 if (os.environ.get('RENDER_SERVICE_ID') or str(os.environ.get('RENDER','')).lower()=='true') and not build_mode:raise RuntimeError('RECEIVER_RECOVERY_BUILD_ONLY')
 if any(p.is_symlink() for p in (root,*root.parents)) or not root.is_dir():raise ValueError('RECEIVER_PHYSICAL_BUILD_ROOT_REQUIRED')
 root=root.resolve()
 if root==Path('/data') or Path('/data') in root.parents:raise ValueError('RECEIVER_PRODUCTION_DATA_PATH_FORBIDDEN')
 manifest=json.loads((HERE/'manifest.json').read_text());raw=(HERE/'delta.json').read_bytes()
 if sha(raw)!=manifest['delta_sha256']:raise ValueError('RECEIVER_DELTA_DRIFT')
 delta=json.loads(raw)
 if delta['before_tree_sha256']!=BASE or delta['after_tree_sha256']!=AFTER:raise ValueError('RECEIVER_TREE_CONTRACT_DRIFT')
 if {row['path'] for row in delta['files']}!=ALLOWED or len(delta['files'])!=len(ALLOWED):raise ValueError('RECEIVER_FILE_SCOPE_DRIFT')
 observed=tree(root)
 if observed==AFTER:return {'status':'PASSED','replayed':True,'after_tree_sha256':AFTER,'database_opened':False}
 if observed!=BASE:raise ValueError('RECEIVER_EXACT_ACCEPTED_PARENT_REQUIRED')
 prepared={}
 for row in delta['files']:
  rel=PurePosixPath(row['path']);path=root.joinpath(*rel.parts)
  if rel.is_absolute() or '..' in rel.parts or path.is_symlink():raise ValueError('RECEIVER_PATH_ESCAPE')
  if row['before_sha256'] is None:
   if path.exists():raise ValueError('RECEIVER_NEW_PATH_EXISTS')
   text=row['new_file']
  else:
   before=path.read_bytes()
   if sha(before)!=row['before_sha256']:raise ValueError('RECEIVER_PARENT_DRIFT:'+row['path'])
   text=before.decode()
   for h in row['hunks']:
    if text.count(h['old'])!=1:raise ValueError('RECEIVER_ANCHOR_DRIFT:'+row['path'])
    text=text.replace(h['old'],h['new'],1)
  after=text.encode()
  if sha(after)!=row['after_sha256'] or manifest['files'][row['path']]!=sha(after):raise ValueError('RECEIVER_RESULT_DRIFT')
  if path.suffix=='.py':compile(after,str(path),'exec')
  prepared[path]=after
 for path,raw in prepared.items():
  fd,tmp=tempfile.mkstemp(prefix='.'+path.name,dir=root)
  with os.fdopen(fd,'wb') as f:f.write(raw)
  os.chmod(tmp,path.stat().st_mode&0o777 if path.exists() else 0o644);os.replace(tmp,path)
 if tree(root)!=AFTER:raise ValueError('RECEIVER_FINAL_TREE_MISMATCH')
 return {'status':'PASSED','replayed':False,'after_tree_sha256':AFTER,'database_opened':False,'schema_changed':False}
