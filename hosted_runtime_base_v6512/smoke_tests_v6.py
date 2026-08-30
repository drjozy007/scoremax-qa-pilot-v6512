"""ScoreMax V6 deterministic written-response regression suite."""
from __future__ import annotations
import io, json, os, sys, tempfile
from pathlib import Path
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from smoke_tests_v5_5 import install_framework_stubs  # noqa: E402


def upload_json(payload, filename='package.json'):
    class Upload:
        def __init__(self): self.filename=filename
        def read(self): return json.dumps(payload).encode('utf-8')
    return Upload()


def image_upload(filename='page.jpg'):
    buf=io.BytesIO()
    img=Image.new('RGB',(1400,1800),'white')
    draw=ImageDraw.Draw(img)
    for y in range(120,1650,55):
        draw.line((80,y,1320,y),fill=(190,190,190),width=2)
        draw.text((110,y-30),f'Biology answer line {y}',fill='black')
    img.save(buf,'JPEG',quality=92); buf.seek(0)
    class Upload:
        def __init__(self): self.filename=filename; self.stream=buf
    return Upload()


class Files(dict):
    def getlist(self,key): return self.get(key,[])


class Form(dict):
    def getlist(self,key):
        v=self.get(key,[])
        return v if isinstance(v,list) else [v]


def main():
    flask,request=install_framework_stubs()
    temp=Path(tempfile.mkdtemp(prefix='scoremax_v6_smoke_'))
    os.environ['SCOREMAX_DB']=str(temp/'scoremax.db')
    os.environ['SCOREMAX_ENV']='local'
    import app
    from written_response_engine import validate_assessment_package, package_signature, mark_written_response

    checks=[]
    def ok(name,condition=True):
        if not condition: raise AssertionError(name)
        checks.append(name); print('PASS:',name)

    app.init(); app.init()
    c=app.db()
    ok('V6 schema is idempotent',c.execute("SELECT COUNT(*) n FROM written_feature_controls").fetchone()['n']==4)
    ok('written response and handwriting are pilot-only by default',
       c.execute("SELECT state FROM written_feature_controls WHERE feature_code='written_response_engine'").fetchone()['state']=='PILOT' and
       c.execute("SELECT state FROM written_feature_controls WHERE feature_code='written_handwriting'").fetchone()['state']=='PILOT')
    ok('exemplar library is hidden by default',c.execute("SELECT state FROM written_feature_controls WHERE feature_code='written_exemplar_library'").fetchone()['state']=='HIDDEN')
    c.close()

    package=json.loads((ROOT/'sample_powerhouse_written_biology_package_v6.json').read_text())
    report=validate_assessment_package(package)
    ok('approved Power House written package validates',report['valid'] and report['question_count']==2)
    signed=json.loads(json.dumps(package)); signed['signature']=package_signature(signed,'written-secret')
    signed_report=validate_assessment_package(signed,shared_secret='written-secret',require_signature=True)
    ok('signed Power House written package verifies for production transport',signed_report['valid'] and signed_report['signature_status']=='VERIFIED')
    tampered=json.loads(json.dumps(package)); tampered['questions'][0]['maximum_marks']=7
    ok('tampered package checksum is rejected',not validate_assessment_package(tampered)['valid'])
    invalid=json.loads(json.dumps(package)); invalid['academic_approval_status']='DRAFT'; invalid.pop('export_checksum',None)
    ok('unapproved package is rejected',not validate_assessment_package(invalid)['valid'])

    full_answer=package['questions'][0]['model_answer']
    result=mark_written_response(package['questions'][0],full_answer)
    ok('approved model answer receives transparent perfect pilot score',result['proposed_mark']==6 and result['status']=='MARK_CONFIRMED' and all(x['status']=='awarded' for x in result['mark_points']))
    keyword_only=mark_written_response(package['questions'][0],'temperature enzyme substrate active site optimum')
    ok('isolated keywords do not receive full explanation marks',keyword_only['proposed_mark']<6 and not keyword_only['command_verb_met'])
    contradicted=mark_written_response(package['questions'][0],full_answer+' Low temperature denatures the enzyme.')
    ok('known contradiction reduces the result and is recorded',contradicted['proposed_mark']<6 and contradicted['contradictions'])

    flask.session.update({'user_id':1,'role':'admin','full_name':'Admin'})
    request.files={'package_file':upload_json(package)}; request.form={}; request.referrer=''
    app.admin_import_written_package()
    c=app.db(); pkg=c.execute("SELECT * FROM written_assessment_packages").fetchone()
    ok('package imports immutably but not active',pkg['local_status']=='IMPORTED' and pkg['export_checksum']==report['checksum'])
    ok('all written questions are imported under the package',c.execute("SELECT COUNT(*) n FROM written_questions WHERE package_id=?",(pkg['id'],)).fetchone()['n']==2)
    c.close()
    request.form={}
    app.admin_activate_written_package(pkg['id'])
    c=app.db(); pkg=c.execute("SELECT * FROM written_assessment_packages WHERE id=?",(pkg['id'],)).fetchone()
    ok('explicit admin activation makes package available',pkg['local_status']=='ACTIVE')

    student_id=c.execute("""INSERT INTO users(system_user_id,role,full_name,email,username,password_hash,academic_level,written_pilot_enabled,access_override_code)
      VALUES('STU-WR-1','student','Written Pilot','written@test','written','x','FSc Part 1',1,'full_access')""").lastrowid
    q1=c.execute("SELECT * FROM written_questions WHERE question_source_id='PH-WR-BIO-ENZ-001-A'").fetchone()
    q2=c.execute("SELECT * FROM written_questions WHERE question_source_id='PH-WR-BIO-ENZ-001-B'").fetchone()
    c.commit()
    ok('pilot student can access while ordinary launch remains off',app.written_feature_available(c,student_id,'written_response_engine'))
    ordinary_id=c.execute("""INSERT INTO users(system_user_id,role,full_name,email,username,password_hash,academic_level,written_pilot_enabled)
      VALUES('STU-WR-2','student','Ordinary Student','ordinary@test','ordinary','x','FSc Part 1',0)""").lastrowid
    c.commit()
    ok('ordinary student cannot access pilot feature',not app.written_feature_available(c,ordinary_id,'written_response_engine'))
    c.close()

    flask.session.clear(); flask.session.update({'user_id':student_id,'role':'student','full_name':'Written Pilot'})
    request.form=Form({'answer_text':full_answer,'attempt_mode':'practice'})
    app.written_submit_typed(q1['id'])
    c=app.db(); attempt=c.execute("SELECT * FROM written_attempts WHERE student_id=? ORDER BY id DESC LIMIT 1",(student_id,)).fetchone()
    run=c.execute("SELECT * FROM written_marking_runs WHERE attempt_id=?",(attempt['id'],)).fetchone()
    ok('typed answer is marked and package/rubric versions are pinned',attempt['current_mark']==6 and attempt['package_version']=='1' and attempt['rubric_version']=='1' and run['result_state']=='MARK_CONFIRMED')
    ok('point-level marking evidence is stored',c.execute("SELECT COUNT(*) n FROM written_mark_point_results WHERE marking_run_id=?",(run['id'],)).fetchone()['n']==6)
    evidence=c.execute("SELECT * FROM written_mastery_evidence WHERE attempt_id=?",(attempt['id'],)).fetchone()
    ok('written marker creates evidence for existing mastery engine rather than awarding mastery directly',evidence and evidence['evidence_status']=='AWAITING_UNSEEN_RECONFIRMATION' and c.execute("SELECT COUNT(*) n FROM mastery_records WHERE student_id=?",(student_id,)).fetchone()['n']==0)
    candidate=c.execute("SELECT * FROM written_exemplar_candidates WHERE attempt_id=?",(attempt['id'],)).fetchone()
    ok('perfect independent answer becomes review candidate but is not published',candidate and candidate['academic_status']=='PENDING_REVIEW' and c.execute("SELECT COUNT(*) n FROM written_exemplars").fetchone()['n']==0)
    c.close()

    # Separate consent first; still no publication.
    request.form=Form({'consent_status':'OPTED_IN','attribution_preference':'ANONYMOUS'})
    app.written_exemplar_consent(candidate['id'])
    c=app.db(); consent=c.execute("SELECT * FROM written_exemplar_consents WHERE candidate_id=?",(candidate['id'],)).fetchone()
    ok('student exemplar consent is explicit and separately stored',consent['consent_status']=='OPTED_IN' and consent['consent_text_version']=='V6-CONSENT-1')
    c.close()
    flask.session.clear(); flask.session.update({'user_id':1,'role':'admin','full_name':'Admin'})
    request.form=Form({'decision':'APPROVED','note':'Clear, accurate and useful full-mark answer.'})
    app.admin_review_written_exemplar(candidate['id'])
    c=app.db(); exemplar=c.execute("SELECT * FROM written_exemplars WHERE candidate_id=?",(candidate['id'],)).fetchone()
    ok('academic approval plus consent creates hidden pre-release exemplar',exemplar and exemplar['publication_status']=='APPROVED_HIDDEN' and exemplar['display_name']=='Anonymous student')
    c.close()
    request.form=Form({'state':'LIVE','required_access_code':'full_access','available_from':'','available_to':''})
    app.admin_update_written_feature('written_exemplar_library')
    c=app.db(); live_exemplar=c.execute("SELECT * FROM written_exemplars WHERE id=?",(exemplar['id'],)).fetchone()
    ok('exam-window release control can publish academically approved consented exemplars',live_exemplar['publication_status']=='PUBLISHED')
    c.close()
    request.form=Form({'state':'HIDDEN','required_access_code':'full_access','available_from':'','available_to':''})
    app.admin_update_written_feature('written_exemplar_library')
    c=app.db(); hidden_again=c.execute("SELECT * FROM written_exemplars WHERE id=?",(exemplar['id'],)).fetchone()
    ok('exemplar library can be withdrawn from ordinary launch without deleting evidence',hidden_again['publication_status']=='APPROVED_HIDDEN')
    c.close()

    # Improvement preserves original and cannot create new formal mastery evidence.
    flask.session.clear(); flask.session.update({'user_id':student_id,'role':'student','full_name':'Written Pilot'})
    request.form=Form({'answer_text':full_answer+' Therefore the causal chain is explicit.'})
    app.written_improve_attempt(attempt['id'])
    c=app.db()
    ok('feedback-led improvement is a new version and never overwrites original',c.execute("SELECT COUNT(*) n FROM written_answer_versions WHERE attempt_id=?",(attempt['id'],)).fetchone()['n']==2 and c.execute("SELECT version_type FROM written_answer_versions WHERE attempt_id=? ORDER BY version_no",(attempt['id'],)).fetchall()[0]['version_type']=='ORIGINAL_TYPED')
    ok('feedback-led improvement does not create another mastery evidence row',c.execute("SELECT COUNT(*) n FROM written_mastery_evidence WHERE attempt_id=?",(attempt['id'],)).fetchone()['n']==1)
    c.close()

    # Unseen submission pins parent and confirms evidence separately.
    request.form=Form({'answer_text':full_answer,'attempt_mode':'practice','parent_attempt_id':str(attempt['id']),'unseen':'1'})
    app.written_submit_typed(q2['id'])
    c=app.db(); unseen=c.execute("SELECT * FROM written_attempts WHERE student_id=? ORDER BY id DESC LIMIT 1",(student_id,)).fetchone()
    unseen_ev=c.execute("SELECT * FROM written_mastery_evidence WHERE attempt_id=?",(unseen['id'],)).fetchone()
    ok('unseen reconfirmation is explicitly linked to original attempt',unseen['parent_attempt_id']==attempt['id'] and unseen['novelty_status']=='unseen_reconfirmation')
    ok('clean unseen answer creates confirmed mastery evidence without direct mastery mutation',unseen_ev and unseen_ev['evidence_status']=='CONFIRMED' and c.execute("SELECT COUNT(*) n FROM mastery_records WHERE student_id=?",(student_id,)).fetchone()['n']==0)
    unseen_candidate=c.execute("SELECT * FROM written_exemplar_candidates WHERE attempt_id=?",(unseen['id'],)).fetchone()
    c.close()
    flask.session.clear(); flask.session.update({'user_id':1,'role':'admin','full_name':'Admin'})
    request.form=Form({'decision':'APPROVED','note':'Approved before consent to test order independence.'})
    app.admin_review_written_exemplar(unseen_candidate['id'])
    c=app.db(); ok('academic approval alone never publishes without opt-in consent',c.execute("SELECT COUNT(*) n FROM written_exemplars WHERE candidate_id=?",(unseen_candidate['id'],)).fetchone()['n']==0); c.close()
    flask.session.clear(); flask.session.update({'user_id':student_id,'role':'student','full_name':'Written Pilot'})
    request.form=Form({'consent_status':'OPTED_IN','attribution_preference':'FIRST_NAME'})
    app.written_exemplar_consent(unseen_candidate['id'])
    c=app.db(); later_exemplar=c.execute("SELECT * FROM written_exemplars WHERE candidate_id=?",(unseen_candidate['id'],)).fetchone()
    ok('consent after academic approval materialises only a hidden pre-release exemplar',later_exemplar and later_exemplar['publication_status']=='APPROVED_HIDDEN' and later_exemplar['display_name']=='Written')
    c.close()

    # Handwriting flow stores original pages and requires OCR confirmation; local admin simulation enables testing.
    request.method='POST'; request.files=Files({'pages':[image_upload()]}); request.form=Form({})
    app.written_handwriting_upload(q1['id'])
    request.method='GET'
    c=app.db(); hand=c.execute("SELECT * FROM written_attempts WHERE student_id=? AND entry_method='handwritten' ORDER BY id DESC LIMIT 1",(student_id,)).fetchone()
    page=c.execute("SELECT * FROM written_upload_pages WHERE attempt_id=?",(hand['id'],)).fetchone()
    job=c.execute("SELECT * FROM written_processing_jobs WHERE attempt_id=?",(hand['id'],)).fetchone()
    ok('handwritten original is privately stored with quality evidence',page and Path(page['storage_path']).exists() and page['original_file_hash'] and page['quality_status'] in ('PASSED','RETAKE_REQUIRED'))
    ok('OCR is an auditable retryable job and production capability is not falsely claimed',job and job['job_type']=='OCR' and job['provider']=='NOT_CONFIGURED')
    c.close()
    flask.session.clear(); flask.session.update({'user_id':1,'role':'admin','full_name':'Admin'})
    request.form=Form({'transcript':full_answer})
    app.admin_written_simulate_ocr(hand['id'])
    c=app.db(); hv=c.execute("SELECT * FROM written_answer_versions WHERE attempt_id=?",(hand['id'],)).fetchone()
    ok('local OCR simulation remains clearly provider-labelled',hv and c.execute("SELECT provider FROM written_processing_jobs WHERE attempt_id=?",(hand['id'],)).fetchone()['provider']=='LOCAL_ADMIN_SIMULATION')
    c.close()
    flask.session.clear(); flask.session.update({'user_id':student_id,'role':'student','full_name':'Written Pilot'})
    request.form=Form({'confirmed_transcript':full_answer})
    app.written_confirm_transcript(hand['id'])
    c=app.db(); hand=c.execute("SELECT * FROM written_attempts WHERE id=?",(hand['id'],)).fetchone(); hv=c.execute("SELECT * FROM written_answer_versions WHERE attempt_id=?",(hand['id'],)).fetchone()
    ok('student-confirmed OCR transcript is frozen with correction audit',hand['result_state']=='MARK_CONFIRMED' and hv['is_frozen']==1 and json.loads(hv['correction_log_json']))

    # Static integration checks from V5 suite remain valid for all new templates/routes.
    from jinja2 import Environment
    env=Environment(); errors=[]
    for path in (ROOT/'templates').glob('*.html'):
        try: env.parse(path.read_text())
        except Exception as exc: errors.append((path.name,str(exc)))
    ok('all V6 Jinja templates parse',not errors)
    c.close()
    print(f'\nScoreMax V6 smoke suite: {len(checks)} checks passed.')
    print('Temporary database:',os.environ['SCOREMAX_DB'])

if __name__=='__main__': main()
