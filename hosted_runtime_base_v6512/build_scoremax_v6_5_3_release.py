"""Build clean ScoreMax V6.5.3 three-system integration admission-rectification candidate."""
from __future__ import annotations
import hashlib, json, zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
OUT=ROOT.parent/'ScoreMax_V6_5_3_Three_System_Integration_Admission_Rectification_Candidate.zip'
EXCLUDE_DIRS={'.venv','__pycache__','internal_live_data','content_intake_uploads','pilot_backups','private_uploads','.git','.pytest_cache'}
EXCLUDE_SUFFIXES={'.pyc','.pyo','.db','.sqlite','.sqlite3','.bak','.tmp'}
ALLOWED_NESTED_ZIPS={'integration_examples/v1_1_0/PH_SM_APPROVED_CONTENT_MANIFEST_DEMO_v1_1_0.zip'}
META_NAMES={'V6_5_3_RELEASE_MANIFEST.json','V6_5_3_FILE_SHA256SUMS.txt'}

def sha(path:Path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
    return h.hexdigest()

def blocked(rel:Path):
    posix=rel.as_posix(); low=posix.lower()
    if set(rel.parts)&EXCLUDE_DIRS: return True
    if rel.suffix.lower() in EXCLUDE_SUFFIXES: return True
    if rel.suffix.lower()=='.zip' and posix not in ALLOWED_NESTED_ZIPS: return True
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
      'release':'ScoreMax V6.5.3 — Three-System Integration Admission Rectification Candidate',
      'status':'PLATFORM_SIDE_INTEGRATION_RECTIFIED_CANDIDATE_PENDING_CROSS_SYSTEM_QUALIFICATION',
      'parent_release':'ScoreMax V6.5.2 — Three-System Integration Admission Rectification Candidate',
      'parent_sha256':'eebdbd043d1c2bb10bb1d1128711e5fcc3347c73307386386d922e90b82feaaf',
      'architecture_change':'systemic_rectification_of_existing_shared_integration_boundary',
      'protected_boundaries':['student_ux','universal_mastery','emergency_direct_intake','learner_payment_referral_authority','power_house_reviewer_boundary'],
      'deterministic_suite_assertions':{'v6_4_inherited':605,'v6_5_compatibility':48,'v6_5_1_rectification':23,'v6_5_1_deep':24,'v6_5_3_behavioral':48,'total':748},
      'scale_gates':{'canonical_300':'PASS_PRESEAL','canonical_1500':'PASS_PRESEAL','emergency_3000':'PASS_PRESEAL'},
      'rubric_only_delivery':'EXPLICIT_UNSUPPORTED_REJECTION',
      'mandatory_external_behavioral_gate':'MUST_RUN_AGAINST_SEALED_BYTES_BEFORE_RETURN',
      'rollback_parent_available':True,
      'known_limitations_file':'V6_5_3_KNOWN_LIMITATIONS.md',
      'academic_reviewer_authority':'Power House',
      'files':hashes,
    }
    mp=ROOT/'V6_5_3_RELEASE_MANIFEST.json'; mp.write_text(json.dumps(manifest,indent=2,sort_keys=True),encoding='utf-8')
    all_for_hash=[x for x in collect(False) if x[1].name!='V6_5_3_FILE_SHA256SUMS.txt']
    cp=ROOT/'V6_5_3_FILE_SHA256SUMS.txt'; cp.write_text('\n'.join(f'{sha(p)}  {rel.as_posix()}' for p,rel in all_for_hash)+'\n',encoding='utf-8')
    files=collect(False); OUT.unlink(missing_ok=True)
    with zipfile.ZipFile(OUT,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p,rel in files: z.write(p,rel.as_posix())
    digest=sha(OUT)
    side=OUT.with_name(OUT.stem+'_SHA256.txt'); side.write_text(f'{digest}  {OUT.name}\n',encoding='utf-8')
    print(OUT); print('files',len(files)); print('sha256',digest); print(side)
if __name__=='__main__': main()
