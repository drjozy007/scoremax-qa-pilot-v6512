"""Materialise the accepted public ScoreMax runtime, then only the Biology receiver delta."""
import argparse,hashlib,importlib.util,json,shutil
from pathlib import Path
REPO=Path(__file__).resolve().parents[1]
EXPECTED='5f4407e82071fc8ac85192b9b8118fdc36d4bef18c1f1159470b9544c24083b9'
PUBLIC='bed7d678f3c43d10d85ab31c699ad78994e0764670890c2fd0c4c77c2629f69c'
def digest(root):
 manifest={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
 return len(manifest),hashlib.sha256(json.dumps(manifest,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def materialize(keep_accepted_source=False):
 root=REPO/'scoremax_runtime_v669b'
 if root.exists() and digest(root)==(261,EXPECTED):return {'replayed':True,'files':261,'runtime_sha256':EXPECTED}
 if not root.exists():
  spec=importlib.util.spec_from_file_location('accepted_public',REPO/'scripts/materialize_scoremax_public_opening_20261026.py')
  module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.materialize()
 assert digest(root)==(261,PUBLIC),'ACCEPTED_PUBLIC_RUNTIME_MISMATCH'
 if keep_accepted_source:
  snapshot=REPO/'biology_accepted_public_runtime_20261027'
  if snapshot.exists():assert digest(snapshot)==(261,PUBLIC)
  else:shutil.copytree(root,snapshot)
 delta=json.loads((REPO/'ux_vnext_overlay/biology_receiver_20261027/source_delta.json').read_text(encoding='utf8'))
 allowed={'app.py','scoremax_integration_v1.py','ux_catalogue_browser.py','templates/test_setup.html','templates/chapter_page.html'}
 assert {row['path'] for row in delta['files']}==allowed
 for row in delta['files']:
  path=root/row['path'];raw=path.read_bytes()
  assert hashlib.sha256(raw).hexdigest()==row['before_sha256'],row['path']
  text=raw.decode('utf8')
  for hunk in row['hunks']:
   assert text.count(hunk['old'])==1,('BIOLOGY_SOURCE_ANCHOR',row['path'])
   text=text.replace(hunk['old'],hunk['new'],1)
  if path.suffix=='.py':compile(text,str(path),'exec')
  assert hashlib.sha256(text.encode()).hexdigest()==row['after_sha256'],row['path']
  path.write_text(text,encoding='utf8',newline='\n')
 assert digest(root)==(261,EXPECTED),'BIOLOGY_RUNTIME_MISMATCH'
 return {'files':261,'runtime_sha256':EXPECTED,'accepted_public_commit':'9df838d46ad82633904f252108ba434be90f9bb3',
         'AI_candidate_applied':False,'power_house_changes':False,'historical_qualifications_replayed':0}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--keep-accepted-source',action='store_true');args=p.parse_args()
 print('SCOREMAX_BIOLOGY_RUNTIME='+json.dumps(materialize(args.keep_accepted_source),sort_keys=True))
