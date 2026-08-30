"""ScoreMax V6.2 deterministic Pilot Readiness & Content Intake smoke suite."""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from smoke_tests_v5_5 import install_framework_stubs
from pilot_readiness_engine import payload_checksum, prompt_pack_signature, validate_prompt_pack, parse_generation_output, feedback_route


class Form(dict):
    def getlist(self,key):
        value=self.get(key,[])
        return value if isinstance(value,list) else [value]


class Upload:
    def __init__(self,data,filename):
        self.filename=filename
        self._data=data if isinstance(data,bytes) else str(data).encode('utf-8')
        self.stream=io.BytesIO(self._data)
    def read(self):
        return self._data
    def save(self,path):
        Path(path).write_bytes(self._data)


def content_csv(qid='V62-BIO-001'):
    headers=['Question ID','Family ID','Variant','Programme','Subject','Chapter','Topic','Sub-topic','Type','Level','Question','A','B','C','D','Answer','Explanation','Country','Qualification','Exam Board','Curriculum Version','Learning Outcome','Concept','Concept ID','Difficulty','Cognitive Skill','Command Word','Marks','Estimated Time Seconds','Misconception Tags','Prerequisite Tags','Source Type','Secure Bank','Rights Status','ScoreMax Ready','Assessment Purpose','Difficulty Source','Family Construct','Family Invariants']
    values=[qid,'V62-FAM-001','A','FSc Part 1','Biology','Biological Molecules','Enzymes','Factors','MCQ','Exam Ready','Which statement best explains enzyme specificity?','The active site is complementary to its substrate','All enzymes bind every substrate','Enzymes are consumed','Temperature never matters','A','The active-site shape and chemistry are complementary to the substrate.','Pakistan','FSc Part 1','Punjab Boards','2026','LO-ENZ-01','Enzyme specificity','BIO-ENZ-SPEC','Moderate','Explain','Explain',1,75,'enzyme consumed','active site|substrate','Power House','No','ScoreMax Original','Yes','practice|test|mock|mastery','authoring','Explain enzyme specificity','active site complementarity|substrate fit']
    def esc(v):
        s=str(v)
        return '"'+s.replace('"','""')+'"' if ',' in s or '"' in s or '|' in s else s
    return (','.join(headers)+'\n'+','.join(esc(v) for v in values)+'\n').encode('utf-8')


def prompt_pack():
    payload={
      'schema_version':'1.0','prompt_pack_id':'PH-PP-FSC-BIO-ENZ-001','prompt_pack_version':'1',
      'status':'APPROVED_FOR_MANUAL_GENERATION','framework':'FSc','framework_version':'2026',
      'subject':'Biology','chapter':'Enzymes','learning_outcome_ids':['LO-ENZ-01'],
      'source_evidence_ids':['SRC-TEXT-001','SRC-SYL-001'],
      'prompt_text':'Generate a governed set of FSc Biology enzyme questions. '+('Preserve the exact learning outcome, evidence IDs, family structure, difficulty, mastery, distractor misconception and structured JSON contract. '*5),
      'expected_output_schema':{'questions':'array'}
    }
    payload['checksum']=payload_checksum(payload)
    return payload


def main():
    flask,request=install_framework_stubs()
    temp=Path(tempfile.mkdtemp(prefix='scoremax_v62_smoke_'))
    os.environ['SCOREMAX_DB']=str(temp/'scoremax.db')
    os.environ['SCOREMAX_ENV']='local'
    import app

    checks=[]
    def ok(name,condition=True):
        if not condition: raise AssertionError(name)
        checks.append(name); print('PASS:',name)

    app.init(); app.init()
    c=app.db()
    ok('V6.2 schema is idempotent',c.execute("SELECT COUNT(*) n FROM pilot_feature_controls").fetchone()['n']==4)
    ok('content intake is pilot-only and Knowledge Hub is hidden by default',
       c.execute("SELECT state FROM pilot_feature_controls WHERE feature_code='content_intake'").fetchone()['state']=='PILOT' and
       c.execute("SELECT state FROM knowledge_feature_controls WHERE feature_code='knowledge_hub'").fetchone()['state']=='HIDDEN')
    ok('existing demo questions are explicitly separated from pilot content',c.execute("SELECT COUNT(*) n FROM questions WHERE is_demo=1 AND content_environment='DEMO'").fetchone()['n']>=5)
    c.close()

    pack=prompt_pack(); report=validate_prompt_pack(pack)
    ok('approved Power House prompt pack validates with checksum',report['valid'] and report['checksum_status']=='VERIFIED')
    signed=json.loads(json.dumps(pack)); signed['signature']=prompt_pack_signature(signed,'prompt-secret')
    signed_report=validate_prompt_pack(signed,shared_secret='prompt-secret',require_signature=True)
    ok('signed prompt transport verifies for production use',signed_report['valid'] and signed_report['signature_status']=='VERIFIED')
    tampered=json.loads(json.dumps(pack)); tampered['chapter']='Changed'
    ok('tampered prompt pack checksum is rejected',not validate_prompt_pack(tampered)['valid'])
    output={'prompt_pack_id':pack['prompt_pack_id'],'prompt_pack_version':'1','questions':[{'question_id':'AI-1','question':'What is an enzyme?'}]}
    ok('manual AI output is structurally linked to the prompt pack',parse_generation_output(json.dumps(output),pack)['valid'])
    ok('academic and technical feedback route to separate authorities',feedback_route('Wrong answer')=='POWER_HOUSE' and feedback_route('Technical failure')=='SCOREMAX')

    flask.session.clear(); flask.session.update({'user_id':1,'role':'admin','full_name':'Admin'})
    request.files={'prompt_pack_file':Upload(json.dumps(pack),'prompt-pack.json')}; request.form=Form({})
    app.admin_prompt_pack_import()
    c=app.db(); stored=c.execute("SELECT * FROM powerhouse_prompt_packs").fetchone()
    ok('prompt bridge imports immutable approved pack',stored and stored['local_status']=='READY_TO_COPY' and stored['payload_checksum']==report['checksum'])
    c.close()
    request.form=Form({}); app.admin_prompt_pack_copy(stored['id'])
    c=app.db(); ok('copy events are audited without changing prompt content',c.execute("SELECT copied_count FROM powerhouse_prompt_packs WHERE id=?",(stored['id'],)).fetchone()['copied_count']==1); c.close()
    request.files={}; request.form=Form({'provider':'Claude','model':'Pilot model','provider_run_id':'RUN-1','generated_output':json.dumps(output)})
    app.admin_generation_output_submit(stored['id'])
    c=app.db(); batch=c.execute("SELECT * FROM powerhouse_generation_batches").fetchone()
    ok('candidate output is stored separately and still requires Power House review',batch['validation_status']=='VALIDATED_CANDIDATE' and batch['item_count']==1)
    c.close()

    # Valid persistent import preview and atomic confirmation.
    request.method='POST'; request.files={'file':Upload(content_csv(),'chapter.csv')}; request.form=Form({'source_system':'POWER_HOUSE_EXPORT','source_prompt_pack_id':pack['prompt_pack_id'],'source_prompt_pack_version':'1'})
    app.admin_import()
    c=app.db(); imp=c.execute("SELECT * FROM content_import_batches ORDER BY id DESC LIMIT 1").fetchone()
    ok('original import file is preserved with its verified checksum',Path(imp['source_file_path']).exists() and __import__('hashlib').sha256(Path(imp['source_file_path']).read_bytes()).hexdigest()==imp['payload_checksum'])
    ok('large-import architecture persists preview rows outside browser session',imp['status']=='PREVIEWED' and imp['row_count']==1 and c.execute("SELECT COUNT(*) n FROM content_import_batch_rows WHERE batch_id=?",(imp['id'],)).fetchone()['n']==1)
    ok('valid preview has no blocking errors',imp['error_count']==0 and imp['valid_count']==1)
    c.close()
    request.form=Form({'batch_id':str(imp['id'])}); request.files={}; app.admin_import_confirm()
    c=app.db(); imp=c.execute("SELECT * FROM content_import_batches WHERE id=?",(imp['id'],)).fetchone(); q=c.execute("SELECT * FROM questions WHERE question_id='V62-BIO-001'").fetchone()
    ok('confirmation creates a verified pre-import backup',imp['backup_record_id'] and c.execute("SELECT integrity_status FROM pilot_backups WHERE id=?",(imp['backup_record_id'],)).fetchone()['integrity_status']=='OK')
    ok('whole batch imports as Draft inactive candidate content',imp['status']=='IMPORTED' and q['status']=='Draft' and q['review_status']=='Draft' and not q['active'] and q['content_environment']=='CANDIDATE')
    ok('import creates usable answer and marking configuration without a full migration pass',json.loads(q['answer_config'])['options'][0]['id']=='A' and json.loads(q['marking_config'])['correct_option_ids']==['A'])
    ok('imported question retains its governed batch lineage',q['source_import_batch_id']==imp['id'])
    c.close()
    request.form=Form({'note':'Smoke rollback before use'}); app.admin_import_batch_rollback(imp['id'])
    c=app.db(); rolled=c.execute("SELECT * FROM content_import_batches WHERE id=?",(imp['id'],)).fetchone()
    ok('unused entire batch can be rolled back after another backup',rolled['status']=='ROLLED_BACK' and not c.execute("SELECT 1 FROM questions WHERE question_id='V62-BIO-001'").fetchone())
    c.close()

    # Used content cannot be erased by a later whole-batch rollback.
    request.method='POST'; request.files={'file':Upload(content_csv('V62-BIO-USED'),'used.csv')}; request.form=Form({'source_system':'POWER_HOUSE_EXPORT'})
    app.admin_import()
    c=app.db(); used_batch=c.execute("SELECT * FROM content_import_batches ORDER BY id DESC LIMIT 1").fetchone(); c.close()
    request.form=Form({'batch_id':str(used_batch['id'])}); request.files={}; app.admin_import_confirm()
    c=app.db(); used_q=c.execute("SELECT id FROM questions WHERE question_id='V62-BIO-USED'").fetchone()['id']; used_student=c.execute("INSERT INTO users(system_user_id,role,full_name,dob,email,username,password_hash,account_status) VALUES('STU-V62-USED','student','Used Student','2001-01-01','used@x','used-v62','x','active')").lastrowid
    used_attempt=c.execute("INSERT INTO attempts(student_id,scope,programme,subject,score,correct_count,total_count,assessment_kind) VALUES(?,'test','FSc','Biology',100,1,1,'pilot')",(used_student,)).lastrowid
    c.execute("INSERT INTO attempt_answers(attempt_id,question_db_id,selected_answer,is_correct) VALUES(?,?, 'A',1)",(used_attempt,used_q)); c.commit(); c.close()
    request.form=Form({'note':'Should be blocked'}); app.admin_import_batch_rollback(used_batch['id'])
    c=app.db(); ok('batch rollback is blocked after assessment evidence uses an imported question',c.execute("SELECT status FROM content_import_batches WHERE id=?",(used_batch['id'],)).fetchone()['status']=='IMPORTED' and c.execute("SELECT 1 FROM questions WHERE id=?",(used_q,)).fetchone()); c.close()

    # Failed background jobs can be safely re-queued with the same idempotency key.
    c=app.db(); job=c.execute("INSERT INTO written_processing_jobs(attempt_id,job_type,state,retry_count,idempotency_key,error_message) VALUES(999,'OCR','FAILED_RETRYABLE',0,'V62-JOB-1','temporary failure')").lastrowid; c.commit(); c.close()
    request.form=Form({}); app.admin_pilot_job_retry(job)
    c=app.db(); retried=c.execute("SELECT * FROM written_processing_jobs WHERE id=?",(job,)).fetchone(); ok('failed processing job is re-queued idempotently',retried['state']=='QUEUED_RETRY' and retried['retry_count']==1 and retried['idempotency_key']=='V62-JOB-1'); c.close()

    # Duplicate file is blocked as a whole, not partially imported.
    c=app.db(); c.execute("INSERT INTO questions(question_id,family_id,programme,subject,chapter,qtype,level,question,answer,status,review_status,active,difficulty,rights_status,scoremax_ready) VALUES('V62-DUP','F','FSc','Biology','C','MCQ','Foundation','Existing?','A','Draft','Draft',0,'Moderate','ScoreMax Original',0)"); c.commit(); c.close()
    request.method='POST'; request.files={'file':Upload(content_csv('V62-DUP'),'duplicate.csv')}; request.form=Form({'source_system':'POWER_HOUSE_EXPORT'})
    app.admin_import()
    c=app.db(); bad=c.execute("SELECT * FROM content_import_batches ORDER BY id DESC LIMIT 1").fetchone()
    ok('existing duplicate question blocks the whole batch',bad['error_count']==1 and bad['status']=='PREVIEWED')
    c.close()
    request.form=Form({'batch_id':str(bad['id'])}); app.admin_import_confirm()
    c=app.db(); ok('blocked batch does not partially import any rows',c.execute("SELECT COUNT(*) n FROM content_import_batch_rows WHERE batch_id=? AND import_status='IMPORTED'",(bad['id'],)).fetchone()['n']==0); c.close()

    # Pilot feedback preserves evidence context and routes academic issue to Power House.
    c=app.db(); student=c.execute("INSERT INTO users(system_user_id,role,full_name,dob,email,username,password_hash,account_status) VALUES('STU-V62','student','Pilot Student','2004-01-01','pilot@x','pilot-v62','x','active')").lastrowid; c.commit(); c.close()
    flask.session.clear(); flask.session.update({'user_id':student,'role':'student','full_name':'Pilot Student'})
    request.method='POST'; request.form=Form({'category':'Incorrect question','severity':'HIGH','description':'The keyed answer conflicts with the approved explanation and syllabus source.','question_id':'1'}); request.files={}
    app.pilot_report_issue()
    c=app.db(); fb=c.execute("SELECT * FROM pilot_feedback").fetchone()
    ok('student issue preserves context and routes academic correction to Power House',fb['routing_target']=='POWER_HOUSE' and fb['severity']=='HIGH' and fb['question_id']==1)
    c.close()

    # Manual and Growth Engine Knowledge drafts require human-controlled status.
    flask.session.clear(); flask.session.update({'user_id':1,'role':'admin','full_name':'Admin'})
    request.method='POST'; request.form=Form({'action':'article','title':'FSc Biology syllabus guide','slug':'fsc-biology-syllabus-guide','summary':'A sourced guide.','body_text':'This is a human-reviewed draft body.','framework':'FSc','framework_version':'2026','subject':'Biology','chapter':'','status':'DRAFT','source_title':'Official syllabus','source_organisation':'Board','source_url':'https://example.invalid/syllabus','rights_status':'LINK_ONLY'}); request.files={}
    app.admin_knowledge()
    c=app.db(); article=c.execute("SELECT * FROM knowledge_articles WHERE source_origin='MANUAL'").fetchone()
    ok('manual Knowledge Hub entry is stored with source governance',article['status']=='DRAFT' and c.execute("SELECT COUNT(*) n FROM knowledge_sources WHERE article_id=?",(article['id'],)).fetchone()['n']==1)
    c.close()
    growth={'draft_id':'GE-1','title':'Enzyme revision guide','summary':'Growth draft','body_text':'Draft body requiring human review.','framework':'FSc','framework_version':'2026','subject':'Biology','chapter':'Enzymes'}
    request.method='POST'; request.form=Form({'action':'growth_import','growth_draft_json':json.dumps(growth)}); request.files={}
    app.admin_knowledge()
    c=app.db(); ga=c.execute("SELECT * FROM knowledge_articles WHERE source_origin='GROWTH_ENGINE'").fetchone()
    ok('Growth Engine intake always becomes a human-review draft',ga and ga['status']=='DRAFT' and c.execute("SELECT status FROM growth_content_intake WHERE converted_article_id=?",(ga['id'],)).fetchone()['status']=='CONVERTED_TO_DRAFT')
    c.close()

    # Demo quarantine requires backup and preserves configuration while removing false pilot evidence.
    c=app.db(); demo=c.execute("INSERT INTO users(system_user_id,role,full_name,dob,email,username,password_hash,account_status,is_demo_account) VALUES('DEMO-V62','student','Demo','2000-01-01','demo@local','demo-v62','x','active',1)").lastrowid
    attempt=c.execute("INSERT INTO attempts(student_id,scope,programme,subject,score,correct_count,total_count,assessment_kind) VALUES(?,'demo','FSc','Biology',100,1,1,'demo_progress')",(demo,)).lastrowid; c.commit(); c.close()
    request.form=Form({'confirmation':'ARCHIVE DEMO DATA'}); app.admin_demo_cleanup()
    c=app.db();
    ok('demo cleanup first creates a verified safety backup',c.execute("SELECT COUNT(*) n FROM demo_cleanup_runs WHERE status='COMPLETED' AND backup_record_id IS NOT NULL").fetchone()['n']==1)
    ok('demo accounts and attempts are removed from pilot evidence without deleting governance configuration',c.execute("SELECT account_status FROM users WHERE id=?",(demo,)).fetchone()['account_status']=='archived_demo' and not c.execute("SELECT 1 FROM attempts WHERE id=?",(attempt,)).fetchone() and c.execute("SELECT COUNT(*) n FROM pilot_feature_controls").fetchone()['n']==4)
    ok('final SQLite integrity check passes',c.execute('PRAGMA integrity_check').fetchone()[0]=='ok')
    c.close()
    request.method='GET'; rendered=app.admin_pilot_analytics(); ok('pilot analytics dashboard executes against the governed schema',rendered and rendered[0]=='render')

    print(f"\nV6.2 smoke suite complete: {len(checks)} checks passed.")
    return len(checks)


if __name__=='__main__':
    main()
