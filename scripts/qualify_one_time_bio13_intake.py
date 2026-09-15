from __future__ import annotations
import base64,csv,gzip,hashlib,io,os,secrets,shutil,sqlite3,sys
from pathlib import Path

BASE=Path(__file__).resolve().parents[1]
RUNTIME=BASE/'scoremax_runtime_v669b'
ROOT=Path('/dev/shm/scoremax-bio13-one-time-qual')
DB=ROOT/'state'/'scoremax.db'
BACKUP=ROOT/'backup'
INTAKE=ROOT/'intake'
ROOT.joinpath('state').mkdir(parents=True,exist_ok=True); BACKUP.mkdir(parents=True,exist_ok=True); INTAKE.mkdir(parents=True,exist_ok=True)
os.environ.update({
 'SCOREMAX_ENV':'local','SCOREMAX_DB':str(DB),'SCOREMAX_PERSISTENT_ROOT':str(ROOT),
 'SCOREMAX_BACKUP_DIR':str(BACKUP),'SCOREMAX_CONTENT_INTAKE_DIR':str(INTAKE),
 'SCOREMAX_SECRET':secrets.token_hex(32),'SCOREMAX_STAGING_SESSION_SECRET':secrets.token_hex(32),
})
sys.path.insert(0,str(RUNTIME))
import app as sm
import ux_one_time_bio13_intake as mod


def build_csv()->bytes:
    fields=['Question ID','Family ID','Variant','Programme','Country','Qualification','Exam Board','Curriculum Version','Subject','Chapter','Chapter Number','Chapter Name','Topic','Sub-topic','Type','Question','A','B','C','D','Answer','Explanation','Level','Difficulty','Learning Outcome','Concept','Cognitive Skill','Command Word','Marks','Estimated Time Seconds','Stimulus / Context','Rights Status','ScoreMax Ready','Assessment Purpose','Difficulty Source','Source Type','Secure Bank','Status','Review Status','R2 Status']
    s=io.StringIO(); w=csv.DictWriter(s,fieldnames=fields); w.writeheader()
    for i in range(1,101):
        w.writerow({'Question ID':f'BIO13-QUAL-{i:03d}','Family ID':f'BIO13-QUAL-F-{(i-1)//4:03d}','Programme':'FSc Part 2','Country':'Pakistan','Qualification':'FSc / Intermediate','Curriculum Version':'2023 Curriculum','Subject':'Biology','Chapter':'13 — Thermoregulation and Osmoregulation','Chapter Number':'13','Chapter Name':'Thermoregulation and Osmoregulation','Topic':'Homeostasis','Type':'MCQ','Question':f'Governed one-time intake fixture {i}?','A':'Correct','B':'B','C':'C','D':'D','Answer':'A','Explanation':'A is correct.','Level':'Foundation','Difficulty':'Easy','Learning Outcome':'Governed fixture outcome','Concept':'Governed fixture family','Cognitive Skill':'Recall','Marks':'1','Estimated Time Seconds':'60','Rights Status':'ScoreMax Original','ScoreMax Ready':'Yes','Assessment Purpose':'practice|test|mock|mastery','Difficulty Source':'Power House governed source','Source Type':'Power House governed SCOREMAX_CREATED','Secure Bank':'Yes','Status':'Ready','Review Status':'AUTO_APPROVED_FOR_RELEASE','R2 Status':''})
    return s.getvalue().encode()


def set_payload(raw:bytes):
    os.environ[mod.PAYLOAD_ENV]=base64.b64encode(gzip.compress(raw,compresslevel=9,mtime=0)).decode()


def main():
    shutil.rmtree(ROOT,ignore_errors=True); ROOT.joinpath('state').mkdir(parents=True); BACKUP.mkdir(); INTAKE.mkdir()
    sm.init()
    # no payload must not mutate content
    os.environ.pop(mod.PAYLOAD_ENV,None)
    mod.run_one_time_bio13_intake(sm)
    c=sm.db(); assert c.execute('SELECT COUNT(*) FROM questions').fetchone()[0]==0; c.close()

    raw=build_csv(); digest=hashlib.sha256(raw).hexdigest()
    mod.EXPECTED_CSV_SHA256=digest
    mod.PROMPT_PACK_ID='BIO13-ONE-TIME-QUALIFICATION'
    mod.PROMPT_PACK_VERSION='2'*64
    set_payload(raw)
    mod.run_one_time_bio13_intake(sm)
    c=sm.db(); qs=c.execute('SELECT * FROM questions ORDER BY id').fetchall(); assert len(qs)==100 and all(q['status']=='Approved' and q['review_status']=='Approved' and int(q['active'] or 0)==1 and q['content_environment']=='PRODUCTION' for q in qs)
    b=c.execute("SELECT * FROM content_import_batches WHERE source_prompt_pack_id=?",(mod.PROMPT_PACK_ID,)).fetchone(); assert b and b['release_status']=='RELEASED_ELIGIBLE' and int(b['released_count'])==100
    batches=c.execute('SELECT COUNT(*) FROM content_import_batches').fetchone()[0]; c.close(); assert batches==1
    # second startup must verify, not duplicate
    mod.run_one_time_bio13_intake(sm)
    c=sm.db(); assert c.execute('SELECT COUNT(*) FROM questions').fetchone()[0]==100 and c.execute('SELECT COUNT(*) FROM content_import_batches').fetchone()[0]==1; c.close()
    # bad payload hash fails closed before mutation
    bad=raw+b'X'; set_payload(bad)
    try: mod.run_one_time_bio13_intake(sm)
    except RuntimeError as e: assert 'payload_sha256_mismatch' in str(e)
    else: raise AssertionError('bad hash did not fail')
    # partial target population fails closed
    set_payload(raw); c=sm.db(); c.execute('DELETE FROM questions WHERE id=(SELECT MIN(id) FROM questions)'); c.commit(); c.close()
    try: mod.run_one_time_bio13_intake(sm)
    except RuntimeError as e: assert 'partial_target_population' in str(e)
    else: raise AssertionError('partial population did not fail')
    print('BIO13_ONE_TIME_INTAKE_QUALIFICATION_PASS no_payload_noop=true imported=100 released=100 scored=100 idempotent_second_start=true bad_hash_fail_closed=true partial_population_fail_closed=true')

if __name__=='__main__': main()
