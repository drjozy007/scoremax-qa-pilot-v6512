"""Materialise the accepted public ScoreMax runtime, then only the Biology receiver delta."""
import argparse,hashlib,importlib.util,json,shutil
from pathlib import Path
REPO=Path(__file__).resolve().parents[1]
EXPECTED='ddb4ee4a1398c0e5ac2300e4711b7a1befadd7e4ef067dfc21bc28de118cdc9c'
PUBLIC='bed7d678f3c43d10d85ab31c699ad78994e0764670890c2fd0c4c77c2629f69c'
def digest(root):
 manifest={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
 return len(manifest),hashlib.sha256(json.dumps(manifest,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def materialize_accepted(keep_accepted_source=False):
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

SHARED_EXPECTED='00c47dd7ee35fe1c1a3254be8a67b54ad1143ccceeaf816d1147a94f45cbbfa1'
EFFECTIVE_PRACTICE_EXPECTED='0aea3be7568b8e6d83d362e0f55a5a64187ebfa1fdd75ef4ca1c45f7dc2cafa8'

def materialize_effective_practice(keep_accepted_source=False):
 root=REPO/'scoremax_runtime_v669b'
 current=digest(root) if root.exists() else None
 if current==(263,EFFECTIVE_PRACTICE_EXPECTED):
  return {'replayed':True,'files':263,'runtime_sha256':EFFECTIVE_PRACTICE_EXPECTED,'learner_activation':False}
 accepted={}
 delta={}
 overlays=REPO/'ux_vnext_overlay/biology_receiver_20261027'
 if current!=(263,SHARED_EXPECTED):
  accepted=materialize_accepted(keep_accepted_source)
  spec=importlib.util.spec_from_file_location('shared_practice_delta',overlays/'shared_practice_runtime.py')
  module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);delta=module.apply(root)
  actual=digest(root)
  assert actual==(263,SHARED_EXPECTED),f'SHARED_PRACTICE_RUNTIME_MISMATCH expected={(263,SHARED_EXPECTED)} observed={actual}'
 spec=importlib.util.spec_from_file_location('effective_practice_mock',overlays/'effective_practice_mock_runtime.py')
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.apply(root)
 actual=digest(root)
 assert actual==(263,EFFECTIVE_PRACTICE_EXPECTED),f'EFFECTIVE_PRACTICE_RUNTIME_MISMATCH observed={actual}'
 return {**accepted,**delta,'files':263,'runtime_sha256':EFFECTIVE_PRACTICE_EXPECTED,
         'accepted_receiver_runtime_sha256':EXPECTED,'effective_practice_official_mock_exclusion':True}
PRACTICE_AVAILABILITY_EXPECTED='9b5803827fc9b19ec879d82bb02968d54df90b8921308dc24dddf97117599419'


def materialize(keep_accepted_source=False):
 root=REPO/'scoremax_runtime_v669b'
 expected=(263,PRACTICE_AVAILABILITY_EXPECTED)
 if root.exists() and digest(root)==expected:
  return {'replayed':True,'files':263,'runtime_sha256':PRACTICE_AVAILABILITY_EXPECTED,'learner_activation':False}
 metadata=materialize_effective_practice(keep_accepted_source)
 source=REPO/'ux_vnext_overlay/biology_receiver_20261027/practice_availability_delta.json'
 rows=json.loads(source.read_text(encoding='utf8'))['files']
 assert {row['path'] for row in rows}=={'app.py','ux_catalogue_browser.py','templates/chapter_page.html'}
 for row in rows:
  path=root/row['path']
  original=path.read_bytes()
  assert hashlib.sha256(original).hexdigest()==row['before_sha256'],row['path']
  text=original.decode('utf8')
  for hunk in row['hunks']:
   assert text.count(hunk['old'])==1,('PRACTICE_AVAILABILITY_SOURCE_ANCHOR',row['path'])
   text=text.replace(hunk['old'],hunk['new'],1)
  if path.suffix=='.py':compile(text,str(path),'exec')
  assert hashlib.sha256(text.encode()).hexdigest()==row['after_sha256'],row['path']
  path.write_text(text,encoding='utf8',newline='\n')
 assert digest(root)==expected,'PRACTICE_AVAILABILITY_RUNTIME_MISMATCH'
 return {**metadata,'files':263,'runtime_sha256':PRACTICE_AVAILABILITY_EXPECTED,
         'practice_availability_access_qualified':True,'learner_activation':False}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--keep-accepted-source',action='store_true');args=p.parse_args()
 print('SCOREMAX_BIOLOGY_RUNTIME='+json.dumps(materialize(args.keep_accepted_source),sort_keys=True))
