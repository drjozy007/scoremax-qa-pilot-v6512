"""Native Flask/SQLite submission qualification using explicit software fixtures.

No source question is declared approved by this test. The separately qualified
signed-admission test owns transport. This exercises native pins, submissions,
saved marking results, unknown-language NULL score, retries and concurrency.
"""
import concurrent.futures
from datetime import datetime
import json
import os
from pathlib import Path
try:
    import resource
except ImportError:
    resource=None
import sys
import tempfile
import time

REPO=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(REPO/'scoremax_runtime_v669b'),str(Path(__file__).parent)]
from test_scored_saq_v1 import fixture_row
import scored_saq_runtime_v1 as boundary


def insert(c,table,row):
    fields={r[1] for r in c.execute('PRAGMA table_info('+table+')')}
    row={k:v for k,v in row.items() if k in fields}
    return c.execute('INSERT INTO '+table+' ('+','.join(row)+') VALUES ('+
                     ','.join('?' for _ in row)+')',tuple(row.values())).lastrowid


def run():
    with tempfile.TemporaryDirectory(prefix='scoremax-native-scored-') as folder:
        state=Path(folder);os.environ.update(SCOREMAX_DB=str(state/'native.db'),SCOREMAX_ENV='local',
            SCOREMAX_SECRET='software-fixture-only-secret-20261122',
            SCOREMAX_STAGING_SESSION_SECRET='software-fixture-only-secret-20261122',
            SCOREMAX_SEND_EMAIL_VERIFICATION='0')
        import app as runtime
        runtime.app.config['TESTING']=True
        c=runtime.db();now=datetime.now().isoformat(timespec='seconds')
        q=fixture_row();q.update(programme='FSc Part 1',subject='Fixture',chapter='1 — Software qualification',
            topic='Software fixture',subtopic='',level='Foundation',difficulty='Foundation',
            status='Approved',active=1,review_status='Approved',rights_status='PUBLIC_DOMAIN',
            family_key='software-scored-family',family_id='software-scored-family',
            question_version=1,ph_projection_owner='POWER_HOUSE',ph_is_auto_markable=1,
            ph_release_id='software-fixture-release',ph_release_version='1',ph_release_checksum_sha256='b'*64)
        curriculum={'market_id':'PK','programme_id':'FSc Part 1','subject_id':'Fixture',
                    'chapter_id':q['ph_chapter_id'],'grade_year_id':'11',
                    'display':{'programme':'FSc Part 1','subject':'Fixture','chapter':q['chapter']}}
        q['ph_curriculum_snapshot_json']=boundary.canonical(curriculum)
        insert(c,'question_families',{'family_key':q['family_key'],'family_id':q['family_id'],
                                    'review_status':'Approved','active':1})
        qid=insert(c,'questions',q);q['id']=qid
        content={'question_family_type':'SHORT_RESPONSE','stem':q['question'],
                 'response_contract':'short_response','marking':{'key_type':'TEXT','key':q['answer'],
                   'marks':2,'rubric':json.loads(q['marking_config'])['rubric']}}
        insert(c,'integration_ph_question_version_store',{
            'question_id':q['ph_question_id'],'question_version_id':q['ph_question_version_id'],
            'question_version_number':1,'question_checksum_sha256':q['ph_question_checksum_sha256'],
            'curriculum_json':boundary.canonical(curriculum),'content_json':boundary.canonical(content),
            'architecture_json':'{}','governance_json':'{}','provenance_json':q['ph_provenance_snapshot_json'],
            'scoremax_projection_json':boundary.canonical(q),'local_question_db_id':qid,'first_admitted_at':now})
        release={'release_id':q['ph_release_id'],'release_version':'1','package_checksum_sha256':'b'*64,
            'manifest_checksum_sha256':'c'*64,'payload_checksum_sha256':'d'*64,'release_status':'RELEASED',
            'local_status':'ACTIVE','market_id':'PK','programme_id':'FSc Part 1','subject_id':'Fixture',
            'chapter_id':q['ph_chapter_id'],'question_count':1,'immutable_payload_json':'{}','admitted_at':now}
        insert(c,'integration_ph_content_releases',release)
        insert(c,'integration_ph_release_question_membership',{
            'release_id':q['ph_release_id'],'release_version':'1','question_id':q['ph_question_id'],
            'question_version_id':q['ph_question_version_id'],'ordinal':0,'admitted_at':now})
        insert(c,'integration_ph_product_activation_authorizations',{
            'release_id':q['ph_release_id'],'release_version':'1','package_checksum_sha256':'b'*64,
            'authorized_by':'software fixture only','authorized_at':now,'reason':'disposable qualification',
            'activation_status':'ACTIVATED'})
        c.commit()
        results=[]
        all_sessions=[]
        responses=[q['answer'],'Criterion beta is satisfied','A valid unfamiliar paraphrase cannot be guessed',
                   'not Criterion alpha is satisfied']
        for concurrency in (1,10,50):
            jobs=[]
            for i in range(concurrency):
                student=insert(c,'users',{'role':'student','full_name':'Software fixture learner',
                    'username':f'fixture-{concurrency}-{i}','academic_level':'FSc Part 1',
                    'session_version':0,'account_status':'active'})
                session_id=runtime.create_assessment_session(c,student,'practice',None,[qid],{
                    'programme':'FSc Part 1','subject':'Fixture','chapters':q['chapter'],
                    'scope':'chapter','level':'Foundation'})
                answer=responses[i%len(responses)]
                runtime.save_assessment(c,session_id,answers={str(qid):answer})
                jobs.append((student,session_id,answer))
            c.commit();all_sessions.extend(jobs)
            def submit(job):
                student,session_id,answer=job;start=time.perf_counter()
                with runtime.app.test_client() as client:
                    with client.session_transaction() as browser_session:
                        browser_session.update(user_id=student,role='student',full_name='Software fixture learner',
                            session_version=0,_csrf_token='software-fixture-csrf')
                    response=client.post(f'/test/session/{session_id}/submit',
                                         data={'_csrf_token':'software-fixture-csrf'})
                    assert response.status_code==302,(response.status_code,response.data[:300])
                    destination=response.headers['Location']
                    repeated=client.post(f'/test/session/{session_id}/submit',
                                         data={'_csrf_token':'software-fixture-csrf'})
                    assert repeated.status_code==302 and repeated.headers['Location']==destination
                    return time.perf_counter()-start
            started=time.perf_counter()
            with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as pool:
                timings=list(pool.map(submit,jobs))
            elapsed=time.perf_counter()-started
            for student,session_id,answer in jobs:
                rows=c.execute('SELECT * FROM attempts WHERE assessment_session_id=?',(session_id,)).fetchall()
                assert len(rows)==1
                marked=c.execute('SELECT * FROM attempt_answers WHERE attempt_id=?',(rows[0]['id'],)).fetchall()
                assert len(marked)==1
                result=json.loads(marked[0]['marking_result_json'])
                if answer==responses[2]:
                    assert rows[0]['score'] is None and marked[0]['marks_awarded'] is None
                    assert rows[0]['mastery_evidence_eligible']==0 and result['status']=='UNSCORED_PENDING_REVIEW'
                else:
                    assert rows[0]['marking_status']=='FINAL'
                    assert marked[0]['ph_question_version_id']==q['ph_question_version_id']
            results.append({'concurrency':concurrency,'learners':len(jobs),'elapsed_seconds':round(elapsed,6),
                'latency_p50_seconds':round(sorted(timings)[len(timings)//2],6),
                'latency_p95_seconds':round(sorted(timings)[min(len(timings)-1,int(len(timings)*.95))],6),
                'maximum_seconds':round(max(timings),6),'idempotent_repeat':'PASSED'})
        integrity=c.execute('PRAGMA integrity_check').fetchone()[0]
        assert integrity=='ok';c.close()
        return {'status':'PASSED','fixture_authority':'SOFTWARE_ONLY_NO_REAL_ACADEMIC_APPROVAL',
                'native_flask_submit_and_sqlite_persistence':True,'results':results,
                'integrity_check':integrity,'max_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss if resource else None,
                'database_bytes':runtime.DB.stat().st_size,'production_mutated':False}


if __name__=='__main__':
    report=run();path=REPO.parent/'evidence/scoremax_native_submission_concurrency_v1.json'
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(report,indent=2));print(json.dumps(report,sort_keys=True))
