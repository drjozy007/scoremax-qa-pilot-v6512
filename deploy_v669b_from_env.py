from __future__ import annotations
import base64,hashlib,io,json,lzma,os,shutil,subprocess,tarfile
from pathlib import Path
import deploy_v669b_runtime

OUT=Path('scoremax_runtime_v669b')
PATHS_FILE=Path('qualification/v6610f_runtime_paths.json')
DELTA_SHA='5f20e0ca9219c40bb0ffe0470c076a911c70ee3c8ddef9e40bdc74b797e131a2'
TREE_SHA='e4de5db8fc107a1e1485550b904040df328f76266518abb183daec029dd9c0c1'
HERO_SHA='ada647f2678abcb08f3423394422cceea8d2c81f5eaf14b57c328bf3d1d591d5'
V6611C_PATCH_XZ_SHA='8994f5b46ca9066c41553d1d9cf581600aa8ec610ea726c2e89d0c007aca315e'
V6611C_PATCH_SHA='69ff734204bf7d4bcac6a68388628acff32b2d722271bfecf95126fad5f696a3'
V6611C_SOURCE_ZIP_SHA='2c70692120bd917006f408db0c6ca5d405a3c5b0fc1a7793bb5de2e9b7b63235'
V6611C_FINAL_RUNTIME_FILES=192
V6611C_ADDED={'account_security_engine.py','production_startup_engine.py','simple_onboarding_engine.py','sqlite_mutation_engine.py'}
V6611C_TARGETS={
'Procfile':('2fc55ce546134e5c427b38166892d054a1ab1f568b8ed109d8d336abf1e52385',148),
'account_security_engine.py':('dc8f342fe902647e50269f76dc6917a8477546b6e2af1bc8648c77cba51e309f',1632),
'app.py':('b4416da9f83943cbc9e607bf048659f46fe47352a571232a592c77b422666ca8',961041),
'feature_availability_engine.py':('766276136260b61365f808a1e103196a86196e24f9d863d972c44caa7080aef4',10983),
'production_content_seed_policy.py':('b49525e54cf32fd671046e890a3526c2ec40950cb28ed7b76fc8ef23a1ff2740',995),
'production_startup_engine.py':('a896c583afc3b921e167c4ae33335d294ceaf98dd9a9cf2f1f70353b8f173e4c',1811),
'referral_attribution_engine.py':('c0d02b4998e3a43fb0724cfb8944ce5d9352816954c1f9dc53483e2061224a7c',11308),
'render.production.candidate.yaml':('0770a28fa38a3c24863bd11ba9c86ba0f4d06aefa55de65e47c6d92fca5c4954',1010),
'science_genius_engine.py':('e84fc261c4e48d988144467a751adca2203cf255af8a78fb960b0113579ca01d',46527),
'scoremax_integration_v1.py':('17e44c96e57fa887c5e687107ffd8ac61ba49d59ade7a7ba3cc44f7d0f7796ad',168542),
'scoremax_production.py':('ab17f8549c8a812aca7cb801f1f1fff3a8f44a678b24365c93ba0988fdce1f29',284),
'scoremax_production_entrypoint.py':('823ad353be5808691229259bf89b8a1798292f1f48191d8ec77cce8b9d0581f1',400),
'simple_onboarding_engine.py':('be2d57fc60ad48d68189c93707805adbfc5974720dfa6f1453ec3c8159639d90',14339),
'sqlite_mutation_engine.py':('ca6975790ec4cb99af74fba934ae8a9aa1665ed3a2125ee980849ff404103eaa',4664),
'static/styles.css':('571f7d7f09b98e530ef6493998d018663658bfab3ef5518170f0210a2e719ce6',113398),
'templates/base.html':('fe2ff7368aa34817707092b007dd750a7a5223674dbfe2910fffbf4eb76e6ccc',28243),
'templates/faq.html':('df9e62b5ff7b5f4233e69839d17d267f43896a259174e7f648d01974c344d678',7348),
'templates/feature_interest.html':('13addf2181e519cbc840459ed4b739c93a8070d33a59df622ec04c8c2c8b2a9d',1882),
'templates/index.html':('0948b3af7c6eda60f7b156b77ad4eb7d6208bb9773673cddd05cd0072c5a86a4',8646),
'templates/student.html':('3ed33b307a52a2dab9d5231fc78d7d61a6ed5ea1dd30027f7a1fd745a04cf320',11920)}

def sha(b): return hashlib.sha256(b).hexdigest()
def fsha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
 return h.hexdigest()

def safe_extract(raw,out,label):
 with tarfile.open(fileobj=io.BytesIO(raw),mode='r:*') as tf:
  root=Path(out).resolve()
  for m in tf.getmembers():
   p=(Path(out)/m.name).resolve()
   if p!=root and root not in p.parents: raise SystemExit(label+'_UNSAFE_TAR:'+m.name)
  tf.extractall(out)

def env_payload(prefix,count,expected):
 keys=sorted(k for k in os.environ if k.startswith(prefix))
 if len(keys)!=count: raise SystemExit(f'{prefix}PART_COUNT_MISMATCH got={len(keys)} expected={count}')
 try: raw=base64.b64decode(''.join(os.environ[k].strip() for k in keys),validate=True)
 except Exception as exc: raise SystemExit(prefix+'BASE64_INVALID:'+type(exc).__name__) from exc
 if sha(raw)!=expected: raise SystemExit(prefix+'SHA_MISMATCH')
 return raw

def git_payload(pattern,expected):
 parts=sorted(Path('qualification').glob(pattern))
 if not parts: raise SystemExit('GIT_PAYLOAD_MISSING:'+pattern)
 try: raw=base64.b64decode(''.join(p.read_text(encoding='ascii').strip() for p in parts),validate=True)
 except Exception as exc: raise SystemExit('GIT_PAYLOAD_BASE64_INVALID:'+type(exc).__name__) from exc
 if sha(raw)!=expected: raise SystemExit('GIT_PAYLOAD_SHA_MISMATCH:'+pattern)
 return raw

def verify_10g(paths):
 actual=sorted(p.relative_to(OUT).as_posix() for p in OUT.rglob('*') if p.is_file())
 if actual!=sorted(paths): raise SystemExit(f'V6610G_PATH_SET_MISMATCH actual={len(actual)} expected={len(paths)}')
 h=hashlib.sha256()
 for rel in sorted(paths):
  p=OUT/rel; h.update(f'{rel}\0{fsha(p)}\0{p.stat().st_size}\n'.encode())
 if h.hexdigest()!=TREE_SHA: raise SystemExit('V6610G_RUNTIME_TREE_SHA_MISMATCH')
 if fsha(OUT/'static/scoremax_intelligence_hero.png')!=HERO_SHA: raise SystemExit('V6610G_HERO_SHA_MISMATCH')
 req=(OUT/'requirements.txt').read_text(encoding='utf-8')
 if 'Flask==3.1.3' not in req or 'Werkzeug==3.1.6' not in req: raise SystemExit('V6610G_DEPENDENCY_PINS_MISSING')
 app=(OUT/'app.py').read_text(encoding='utf-8'); integ=(OUT/'scoremax_integration_v1.py').read_text(encoding='utf-8')
 if "SCOREMAX_RELEASE_VERSION='6.6.10G'" not in app or '6.6.10G' not in integ: raise SystemExit('V6610G_RELEASE_IDENTITY_MISSING')

def main():
 # Reconstruct and independently verify exact governed 6.6.9B from Git-native runtime_payload + inherited verified hero.
 deploy_v669b_runtime.main()
 paths=set(json.loads(PATHS_FILE.read_text(encoding='utf-8')))
 paths.discard('README_SCOREMAX_V6_6_9B.md'); paths.discard('V6_6_9B_PACKAGE_MANIFEST.json'); paths.add('production_content_seed_policy.py')
 if len(paths)!=188: raise SystemExit(f'V6610G_PATH_CONTRACT_INVALID got={len(paths)} expected=188')
 for rel in ('README_SCOREMAX_V6_6_9B.md','V6_6_9B_PACKAGE_MANIFEST.json'):
  p=OUT/rel
  if p.exists(): p.unlink()
 delta=env_payload('V6610G_DELTA_PART_',4,DELTA_SHA)
 tmp=Path('/tmp/v6610g_delta'); shutil.rmtree(tmp,ignore_errors=True); tmp.mkdir(parents=True); safe_extract(delta,tmp,'V6610G_DELTA')
 patch=tmp/'v669b_to_v6610g_runtime.patch'
 if not patch.is_file(): raise SystemExit('V6610G_DELTA_PATCH_MISSING')
 cp=subprocess.run(['patch','-d',str(OUT),'-p1','--batch','--forward'],input=patch.read_bytes(),stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 if cp.returncode!=0: raise SystemExit('V6610G_PATCH_FAILED:'+cp.stdout.decode(errors='replace')[-1600:])
 for p in sorted((tmp/'new').rglob('*')):
  if p.is_file():
   dst=OUT/p.relative_to(tmp/'new'); dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(p,dst)
 verify_10g(paths)
 patch_xz=git_payload('v6611c_patch_part_*.b64',V6611C_PATCH_XZ_SHA)
 try: patch11=lzma.decompress(patch_xz)
 except Exception as exc: raise SystemExit('V6611C_PATCH_XZ_INVALID:'+type(exc).__name__) from exc
 if sha(patch11)!=V6611C_PATCH_SHA: raise SystemExit('V6611C_PATCH_SHA_MISMATCH')
 cp=subprocess.run(['patch','-d',str(OUT),'-p1','--batch','--forward'],input=patch11,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
 if cp.returncode!=0: raise SystemExit('V6611C_PATCH_FAILED:'+cp.stdout.decode(errors='replace')[-1600:])
 final=set(paths)|V6611C_ADDED
 actual=sorted(p.relative_to(OUT).as_posix() for p in OUT.rglob('*') if p.is_file())
 if actual!=sorted(final) or len(actual)!=V6611C_FINAL_RUNTIME_FILES: raise SystemExit(f'V6611C_PATH_SET_MISMATCH actual={len(actual)} expected={V6611C_FINAL_RUNTIME_FILES}')
 for rel,(want,size) in V6611C_TARGETS.items():
  p=OUT/rel
  if not p.is_file() or p.stat().st_size!=size or fsha(p)!=want: raise SystemExit('V6611C_TARGET_MISMATCH:'+rel)
 if fsha(OUT/'static/scoremax_intelligence_hero.png')!=HERO_SHA: raise SystemExit('V6611C_HERO_SHA_MISMATCH')
 app=(OUT/'app.py').read_text(encoding='utf-8'); integ=(OUT/'scoremax_integration_v1.py').read_text(encoding='utf-8')
 if "SCOREMAX_RELEASE_VERSION='6.6.11C'" not in app or "SCOREMAX_INTEGRATION_RELEASE='6.6.11C'" not in integ: raise SystemExit('V6611C_RELEASE_IDENTITY_MISSING')
 if (OUT/'Procfile').read_text(encoding='utf-8').splitlines()[0].strip()!='web: python scoremax_production_entrypoint.py': raise SystemExit('V6611C_PROCFILE_NOT_CANONICAL')
 if 'startCommand: python scoremax_production_entrypoint.py' not in (OUT/'render.production.candidate.yaml').read_text(encoding='utf-8'): raise SystemExit('V6611C_RENDER_START_NOT_CANONICAL')
 print('V6611C_HOSTED_RUNTIME_VERIFIED','lineage=GIT_NATIVE_9B_TO_10G_TO_11C',f'parent_runtime_tree_sha256={TREE_SHA}',f'source_zip_sha256={V6611C_SOURCE_ZIP_SHA}',f'patch_xz_sha256={V6611C_PATCH_XZ_SHA}',f'patch_sha256={V6611C_PATCH_SHA}',f'files={len(final)}','release=6.6.11C','status=PRE_DOMAIN_PREQUALIFICATION_CANDIDATE_NOT_FROZEN')

if __name__=='__main__': main()
