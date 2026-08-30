"""Build clean ScoreMax V6.5.1 three-system integration rectification candidate."""
from __future__ import annotations
import hashlib, json, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
OUT=ROOT.parent/'ScoreMax_V6_5_1_Three_System_Integration_Rectification_Candidate.zip'
EXCLUDE_DIRS={'.venv','__pycache__','internal_live_data','content_intake_uploads','pilot_backups','private_uploads','.git','.pytest_cache'}
EXCLUDE_SUFFIXES={'.pyc','.pyo','.db','.sqlite','.sqlite3','.bak','.tmp','.zip'}
EXCLUDE_NAMES={
 'session_secret.txt','session_secret_v640.txt','session_secret_v650.txt','session_secret_v651.txt',
 'run_v6_5_acceptance.py','build_scoremax_v6_5_release.py',
 'V6_4_0_RELEASE_MANIFEST.json','V6_4_0_FILE_SHA256SUMS.txt',
 'V6_5_0_RELEASE_MANIFEST.json','V6_5_0_FILE_SHA256SUMS.txt',
 'build_scoremax_v6_4_release.py','build_scoremax_v6_3_1_release.py','build_scoremax_v6_3_release.py',
 'start_scoremax_v6_4_internal_live.bat','INSTALL_AND_START_SCOREMAX_V6_4.bat','BACKUP_SCOREMAX_V6_4.bat','RESTORE_SCOREMAX_V6_4.bat','RUN_SCOREMAX_V6_4_ACCEPTANCE.bat','START_HERE_V6_4.txt',
 'start_scoremax_v6_5_internal_live.bat','INSTALL_AND_START_SCOREMAX_V6_5.bat','BACKUP_SCOREMAX_V6_5.bat','RESTORE_SCOREMAX_V6_5.bat','RUN_SCOREMAX_V6_5_ACCEPTANCE.bat','START_HERE_V6_5.txt',
 'scoremax_internal_live_v650.py','scoremax_internal_live_backup_v650.py',
}
OLD_LAUNCH_PREFIXES=(
 'start_scoremax_v6.bat','start_scoremax_v6_1.bat','start_scoremax_v6_2.bat','start_scoremax_v6_2_1.bat','start_scoremax_v6_2_2.bat','start_scoremax_v6_2_3.bat','start_scoremax_v6_2_4.bat','start_scoremax_v6_2_5.bat','start_scoremax_v6_2_6.bat','start_scoremax_v6_2_7.bat','start_scoremax_v6_2_7_1.bat','start_scoremax_v6_2_7_2.bat','start_scoremax_v6_2_8.bat','start_scoremax_v6_2_8_1.bat','start_scoremax_v6_3_internal_live.bat','start_scoremax_v6_3_1_internal_live.bat','start_scoremax_v6_3_2_internal_live.bat')
ALLOW_IMAGES={'static/scoremax_intelligence_hero.png'}
META_NAMES={'V6_5_1_RELEASE_MANIFEST.json','V6_5_1_FILE_SHA256SUMS.txt'}

def sha(path:Path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
 return h.hexdigest()

def blocked(rel:Path):
 posix=rel.as_posix(); low=posix.lower()
 if set(rel.parts)&EXCLUDE_DIRS: return True
 if rel.name in EXCLUDE_NAMES or rel.name in OLD_LAUNCH_PREFIXES: return True
 # Historical raw acceptance/scale run transcripts contain disposable bootstrap credentials.
 # Keep governed summaries, not credential-bearing run logs, in release artifacts.
 uname=rel.name.upper()
 if '_RUN_' in uname or uname.endswith('_RUN.TXT') or 'ACCEPTANCE_RUN' in uname: return True
 if rel.suffix.lower() in EXCLUDE_SUFFIXES: return True
 if rel.suffix.lower() in {'.jpg','.jpeg','.png','.webp'} and posix not in ALLOW_IMAGES: return True
 if low.endswith('.env') or '/.env' in low or 'session_secret' in low: return True
 return False

def collect(exclude_meta=False):
 out=[]
 for p in ROOT.rglob('*'):
  if not p.is_file(): continue
  rel=p.relative_to(ROOT)
  if blocked(rel): continue
  if exclude_meta and rel.name in META_NAMES: continue
  out.append((p,rel))
 return sorted(out,key=lambda x:x[1].as_posix())

def main():
 for name in META_NAMES: (ROOT/name).unlink(missing_ok=True)
 base=collect(exclude_meta=True)
 hashes={rel.as_posix():sha(p) for p,rel in base}
 manifest={
  'release':'ScoreMax V6.5.1 — Three-System Integration Rectification Candidate',
  'status':'PLATFORM_SIDE_INTEGRATION_RECTIFIED_CANDIDATE_PENDING_CROSS_SYSTEM_QUALIFICATION',
  'parent_release':'ScoreMax V6.5.0 — Three-System Integration Platform Candidate',
  'parent_sha256':'8a32da65da5d389e69b5771f495b81047dee347cbc7705ee5951536aa111f0e2',
  'contract_compatibility':{'v1.0.0_inline':'SUPPORTED','v1.0.0_manifest_pull':'EXPLICIT_CONTRACT_CONFLICT','v1.1.0_inline':'SUPPORTED','v1.1.0_manifest_pull':'SUPPORTED','v1.1.0_withdraw':'SUPPORTED'},
  'deterministic_checks':699,'v6_4_inherited_checks':605,'v6_5_compatibility_checks':48,'v6_5_1_focused_checks':22,'v6_5_1_deep_checks':24,
  'integration_control_adversarial':{'checks':18,'confirmed_defects':0,'result':'PASS_RECTIFIED'},
  'canonical_integration_scale':{'300_questions':'PASS','1500_questions':'PASS','real_power_house_release':'PENDING_CROSS_SYSTEM'},
  'emergency_direct_intake':{'max_rows':3000,'regression':'PASS','role':'business_continuity_fallback'},
  'mastery_simulation':{'synthetic_learners':10000,'randomized_invariant_checks':200000,'detailed_failures':0,'fuzz_failures':0,'qa_to_live_leakage':0},
  'migration':{'exact_v6_5_0_db_upgrade':'PASS','v6_5_1_backup_restore':'PASS'},
  'rollback_parent_available':True,
  'known_limitations':['real_governed_power_house_vertical_slice_pending','real_growth_engine_counterparty_receipts_pending','v1_0_manifest_pull_frozen_schema_conflict','hosted_postgresql_domain_browser_smtp_pending','cross_system_integrated_adversarial_audit_pending'],
  'academic_reviewer_authority':'Power House',
  'files':hashes,
 }
 mp=ROOT/'V6_5_1_RELEASE_MANIFEST.json'; mp.write_text(json.dumps(manifest,indent=2,sort_keys=True),encoding='utf-8')
 all_for_hash=[x for x in collect(False) if x[1].name!='V6_5_1_FILE_SHA256SUMS.txt']
 cp=ROOT/'V6_5_1_FILE_SHA256SUMS.txt'; cp.write_text('\n'.join(f'{sha(p)}  {rel.as_posix()}' for p,rel in all_for_hash)+'\n',encoding='utf-8')
 files=collect(False); OUT.unlink(missing_ok=True)
 with zipfile.ZipFile(OUT,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
  for p,rel in files: z.write(p,rel.as_posix())
 digest=sha(OUT); side=OUT.with_name(OUT.stem+'_SHA256.txt'); side.write_text(f'{digest}  {OUT.name}\n',encoding='utf-8')
 print(OUT); print('files',len(files)); print('sha256',digest); print(side)
if __name__=='__main__': main()
