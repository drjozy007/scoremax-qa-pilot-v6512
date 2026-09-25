"""Isolated native WSGI assessment/PH-contract adversarial regression. Never uses live data."""
from __future__ import annotations
import argparse,copy,hashlib,json,os,socket,sqlite3,sys,tempfile,unittest
from datetime import datetime,timezone,timedelta
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit,parse_qs
from html.parser import HTMLParser

ROOT=Path(__file__).resolve().parents[1]/'scoremax_runtime_v669b'
STATE=tempfile.TemporaryDirectory(prefix='scoremax-assessment-repair-');BASE=Path(STATE.name)
for key in tuple(os.environ):
    if key.startswith(('SCOREMAX_','POWER_HOUSE_','GROWTH_ENGINE_')):del os.environ[key]
os.environ.update({'SCOREMAX_ENV':'production','SCOREMAX_SECRET':'synthetic-assessment-repair-no-live-secret',
 'SCOREMAX_STAGING_SESSION_SECRET':'synthetic-assessment-repair-no-live-secret','SCOREMAX_DB':str(BASE/'initial.db'),
 'SCOREMAX_PERSISTENT_ROOT':str(BASE),'SCOREMAX_BACKUP_DIR':str(BASE/'backup'),'SCOREMAX_CONTENT_INTAKE_DIR':str(BASE/'intake'),
 'SCOREMAX_SMTP_HOST':'smtp.invalid','SCOREMAX_SMTP_FROM':'qualification@scoremax.test','SCOREMAX_PUBLIC_BASE_URL':'https://localhost',
 'WEB_CONCURRENCY':'1','SCOREMAX_INSTANCE_COUNT':'1','SCOREMAX_REQUIRE_EMAIL_VERIFICATION':'0','SCOREMAX_ENFORCE_PAYWALL':'0',
 'SCOREMAX_BOOTSTRAP_ADMIN_PASSWORD':'Synthetic-Only-Test-Password!'})
def deny(*args,**kwargs):raise RuntimeError('QUALIFICATION_NETWORK_DISABLED')
socket.socket.connect=deny;socket.socket.connect_ex=deny
sys.path.insert(0,str(ROOT))
import scoremax_production as production
import app as sm
import scoremax_integration_v1 as integration
import ux_constructed_auto_marker as marker
import ux_content_reviewer as reviewer
from werkzeug.datastructures import MultiDict

DETAILS=[]
RUBRIC={'version':'SM-RUBRIC-CLAUSES-1','required_mark_points':[
 {'id':'P1','description':'Molecules collide with the particle.','marks':1,
  'accepted_phrases':['Molecules collide with the particle.'],
  'acceptable_paraphrases':['The particle is struck by surrounding molecules.']},
 {'id':'P2','description':'Unequal impacts cause irregular motion.','marks':1,
  'accepted_phrases':['Unequal molecular impacts cause irregular motion.'],
  'acceptable_paraphrases':['The particle moves randomly because impacts are unequal.']}],
 'contradictions':[{'phrase':'No molecules collide with the particle.','point_ids':['P1']},
                   {'phrase':'The impacts are always equal.','point_ids':['P2']}]}

def rubric_question():
    return question('Constructed Response','',{}, {'marks':2,'auto_markable':True,'rubric':copy.deepcopy(RUBRIC)},marks=2)

def question(qtype='MCQ',answer='B',ac=None,mc=None,marks=1):
    return {'qtype':qtype,'question':'[SYNTHETIC] Give the answer.','answer':answer,'marks':marks,'command_word':'state',
      'answer_config':json.dumps(ac if ac is not None else {'options':[{'id':'A','text':'ONE'},{'id':'B','text':'TWO'}]}),
      'marking_config':json.dumps(mc if mc is not None else {'marks':marks,'auto_markable':True,'correct_option_ids':['B']}),
      'misconception_tags':'[]','option_a':'ONE','option_b':'TWO','option_c':'','option_d':'','question_version':1}

SPECS={
 'MCQ':(question(),{'answer':'B'}),
 'TF':(question('True False','TRUE',{'options':[{'id':'TRUE','text':'True'},{'id':'FALSE','text':'False'}]}, {'auto_markable':True,'marks':1,'correct_option_ids':['TRUE']}),{'answer':'TRUE'}),
 'MR':(question('Multiple Select','A,C',{'options':[{'id':x,'text':x} for x in 'ABC']},{'auto_markable':True,'marks':1,'correct_option_ids':['A','C']}),{'answer':['A','C']}),
 'NUM':(question('Numerical','-314',{}, {'marks':1,'auto_markable':True,'correct_value':-314,'tolerance':0}),{'answer':'-314'}),
 'FIB':(question('Fill Blank','viscosity',{'accepted_answers':['viscosity']},{'marks':1,'auto_markable':True}),{'answer':'viscosity'}),
 'MATCH':(question('Matching','',{'left_items':[{'id':'L1','text':'one'},{'id':'L2','text':'two'}],'right_options':[{'id':'R1','text':'1'},{'id':'R2','text':'2'}]}, {'marks':1,'auto_markable':True,'correct_mapping':{'L1':'R1','L2':'R2'}}),{'match::L1':'R1','match::L2':'R2'}),
 'ORDER':(question('Ordering','',{'ordering_items':[{'id':'O1','text':'first'},{'id':'O2','text':'second'}]}, {'marks':1,'auto_markable':True,'correct_order':['O1','O2']}),{'order::O1':'1','order::O2':'2'}),
 'WRITTEN':(rubric_question(),{'answer':'Molecules collide with the particle. Unequal molecular impacts cause irregular motion.'})}

class Tags(HTMLParser):
    def __init__(self,text):super().__init__();self.tags=[];self.feed(text)
    def handle_starttag(self,tag,attrs):self.tags.append((tag,dict(attrs)))

with sm.db() as c:
    for n in (1,2):
        c.execute("INSERT INTO users(system_user_id,role,full_name,email,username,account_status,session_version,academic_level,active_programme,subjects) VALUES(?,'student',?,?,?,'active',0,'FSc Part 1','FSc Part 1','Physics,Chemistry')",(f'SYN-STU-{n}',f'Synthetic student {n}',f'syn-{n}@scoremax.test',f'syn-{n}'))
    c.commit()
SNAPSHOT=BASE/'snapshot.db'
with sm.db() as src,sqlite3.connect(SNAPSHOT) as dst:src.backup(dst)

class AssessmentRepair(unittest.TestCase):
    def setUp(self):
        self.db=BASE/(self._testMethodName+'.db')
        with sqlite3.connect(SNAPSHOT) as src,sqlite3.connect(self.db) as dst:src.backup(dst)
        sm.DB=self.db;os.environ['SCOREMAX_DB']=str(self.db)
        self.c=sm.db();self.uid=self.c.execute("SELECT id FROM users WHERE username='syn-1'").fetchone()[0]
        self.client=self.client_for('syn-1')
    def tearDown(self):
        self.c.rollback();self.c.close()
    def client_for(self,name):
        row=self.c.execute('SELECT * FROM users WHERE username=?',(name,)).fetchone();client=sm.app.test_client()
        with client.session_transaction() as s:s.update(user_id=row['id'],role=row['role'],full_name=row['full_name'],session_version=0,_csrf_token='synthetic-csrf')
        return client
    def insert(self,q):
        q=copy.deepcopy(q);n=self.c.execute('SELECT COUNT(*) FROM questions').fetchone()[0]+1
        q.update(question_id=f'SYN-Q-{n}',family_id=f'SYN-F-{n}',programme='FSc Part 1',qualification='FSc Part 1',country='Pakistan',subject='Physics',chapter='Measurements',topic='Synthetic',learning_outcome='SYN-LO',concept='Synthetic',level='Exam Ready',difficulty='Moderate',status='Approved',review_status='Approved',active=1,is_demo=0,scoremax_ready=1,ph_projection_owner='',source_type='ISOLATED_SYNTHETIC_TEST',rights_status='ScoreMax Original')
        q['family_key']=sm.upsert_question_family(self.c,q,review_status='Approved',active=1)
        columns={r[1] for r in self.c.execute('PRAGMA table_info(questions)')};q={k:v for k,v in q.items() if k in columns}
        qid=self.c.execute(f'INSERT INTO questions({",".join(q)}) VALUES({",".join("?" for _ in q)})',tuple(q.values())).lastrowid;self.c.commit();return qid
    def start(self,qids,rules=None):
        meta={'programme':'FSc Part 1','subject':'Physics','chapters':'Measurements','scope':'chapter','assessment_kind':'synthetic_regression'}
        if rules is not None:meta['blueprint_snapshot']={'marking_rules':rules}
        return sm.create_assessment_session(self.c,self.uid,'practice',None,qids,meta)
    def post(self,aid,form):
        return self.client.post(f'/test/session/{aid}',data={'_csrf_token':'synthetic-csrf','response_present':'1','action':'review',**form},base_url='https://localhost')
    def submit(self,aid,client=None):
        return (client or self.client).post(f'/test/session/{aid}/submit',data={'_csrf_token':'synthetic-csrf'},base_url='https://localhost')
    def attempt(self,aid):return self.c.execute('SELECT * FROM attempts WHERE assessment_session_id=?',(aid,)).fetchone()
    def saved(self,aid):return json.loads(self.c.execute('SELECT saved_answers FROM assessment_sessions WHERE id=?',(aid,)).fetchone()[0])
    def ph_fixture(self,activate=True,historical=False,source_content=None):
        env=json.loads((ROOT/'integration_examples/PH_SM_APPROVED_CONTENT_V1.example.json').read_text())
        now=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z');q=env['payload']['questions'][0];rel=env['payload']['release']
        rel.update(release_id='SYN-RELEASE',release_version='1',generated_at=now,effective_at=now)
        q.update(question_id='SYN-PH-Q',question_version_id='SYN-PH-Q-v1',question_version_number=1,supersedes_question_version_id=None,effective_from=now)
        q['content']['stem']='[SYNTHETIC] Select TWO.'
        q['content']['options']=[{'option_id':'A','text':'ONE','is_display_only':False},{'option_id':'B','text':'TWO','is_display_only':False}]
        q['content']['marking']['key']='B'
        if source_content is not None: q['content'].update(source_content)
        q['question_checksum_sha256']=integration._object_checksum(q,'question_checksum_sha256')
        env.update(message_id='SYN-PH-MSG',idempotency_key='SYN-PH-IDEMPOTENCY',occurred_at=now,sent_at=now)
        env['payload_checksum_sha256']=integration.payload_checksum(env['payload'])
        receipt,status=integration.admit_content_envelope(self.c,env,env['payload_checksum_sha256']);self.c.commit()
        self.assertEqual(status,202,receipt)
        if historical:
            # Historical shape fixture only: intentionally old frozen type with source options.
            v=self.c.execute('SELECT * FROM integration_ph_question_version_store').fetchone();p=json.loads(v['scoremax_projection_json']);content=json.loads(v['content_json'])
            content['question_family_type']='TWO_TIER_DIAGNOSTIC_SINGLE_BEST_PAIR';content['exam_question_type']='TWO_TIER_DIAGNOSTIC_SINGLE_BEST_PAIR'
            content['marking'].update(key_type='TEXT',accepted_answers=['B'])
            p.update(qtype='Fill Blank',ph_response_contract='fill_blank',answer='B',answer_config=json.dumps({'accepted_answers':['B']}),marking_config=json.dumps({'marks':1,'auto_markable':True,'key_type':'TEXT'}))
            self.c.execute('UPDATE integration_ph_question_version_store SET content_json=?,scoremax_projection_json=?',(json.dumps(content),json.dumps(p)));self.c.commit()
        mid=self.c.execute('SELECT id FROM integration_ph_release_question_membership').fetchone()[0]
        if not activate:return mid,env
        result=integration.authorize_product_activation(self.c,rel['release_id'],rel['release_version'],rel['package_checksum_sha256'],'SYNTHETIC-OWNER','Isolated regression only');self.c.commit()
        self.assertEqual(result['status'],'ACTIVE',result)
        row=self.c.execute('SELECT * FROM questions WHERE ph_question_id=?',('SYN-PH-Q',)).fetchone()
        return row['id'],env

    def test_native_eight_response_journeys(self):
        for name,(q,form) in SPECS.items():
            with self.subTest(name=name):
                qid=self.insert(q);aid=self.start([qid]);r=self.client.get(f'/test/session/{aid}',base_url='https://localhost')
                self.assertEqual(r.status_code,200)
                controls=[attrs for tag,attrs in Tags(r.text).tags if tag in {'input','select','textarea'} and attrs.get('name','').startswith(('answer','match::','order::')) and attrs.get('type')!='hidden']
                self.assertTrue(controls)
                self.assertEqual(self.post(aid,form).status_code,302)
                self.assertIn(str(qid),self.saved(aid))
                response=self.submit(aid);a=self.attempt(aid);self.assertEqual(response.status_code,302)
                self.assertIsNotNone(a);self.assertEqual(a['score'],100);self.assertEqual(a['total_marks_awarded'],q['marks'])
                self.assertEqual(a['marking_status'],'FINAL');self.assertEqual(a['mastery_evidence_eligible'],1)
                ans=self.c.execute('SELECT * FROM attempt_answers WHERE attempt_id=?',(a['id'],)).fetchone()
                result=json.loads(ans['marking_result_json']);self.assertTrue(result['confirmed']);self.assertTrue(result['evidence_eligible'])
                self.assertEqual(self.submit(aid).status_code,302)
                self.assertEqual(self.c.execute('SELECT COUNT(*) FROM attempts WHERE assessment_session_id=?',(aid,)).fetchone()[0],1)
                page=self.client.get(response.location,base_url='https://localhost');self.assertEqual(page.status_code,200)
                DETAILS.append({'journey':name,'earned':a['total_marks_awarded'],'max':a['maximum_marks'],'score':a['score'],'saved_submitted_replayed':True})

    def test_clearing_all_eight_response_types(self):
        for name,(q,form) in SPECS.items():
            with self.subTest(name=name):
                qid=self.insert(q);aid=self.start([qid]);self.post(aid,form)
                self.assertIn(str(qid),self.saved(aid))
                self.assertEqual(self.post(aid,{}).status_code,302)
                self.assertNotIn(str(qid),self.saved(aid))
                self.assertEqual(self.submit(aid).status_code,302)
                self.assertEqual(self.attempt(aid)['score'],0)
                DETAILS.append({'clearing':name,'old_answer_removed':True})

    def test_omitted_response_without_sentinel_preserves_saved_answer(self):
        qid=self.insert(SPECS['NUM'][0]);aid=self.start([qid]);self.post(aid,{'answer':'-314'})
        r=self.client.post(f'/test/session/{aid}',data={'_csrf_token':'synthetic-csrf','action':'previous'},base_url='https://localhost')
        self.assertEqual(r.status_code,200);self.assertEqual(self.saved(aid)[str(qid)],'-314')

    def test_clearing_one_question_does_not_erase_another(self):
        ids=[self.insert(SPECS['NUM'][0]),self.insert(SPECS['FIB'][0])];aid=self.start(ids)
        self.post(aid,{'answer':'-314','action':'next'});self.post(aid,{'answer':'viscosity'})
        self.post(aid,{})
        self.assertEqual(self.saved(aid),{str(ids[0]):'-314'})

    def test_malformed_order_rollback_preserves_previous_response(self):
        qid=self.insert(SPECS['ORDER'][0]);aid=self.start([qid]);self.post(aid,SPECS['ORDER'][1]);before=self.saved(aid)
        for form in ({'order::O1':'1','order::O2':'1'},{'order::O1':'cat'},{'answer':'{"bad":"object"}'}):
            self.assertEqual(self.post(aid,form).status_code,409);self.assertEqual(self.saved(aid),before)

    def test_duplicate_single_answer_values_are_rejected(self):
        qid=self.insert(SPECS['MCQ'][0]);aid=self.start([qid])
        self.assertEqual(self.post(aid,{'answer':['A','B']}).status_code,409);self.assertEqual(self.saved(aid),{})

    def test_multimark_partial_credit_uses_mark_percentage(self):
        qid=self.insert(rubric_question());aid=self.start([qid]);self.post(aid,{'answer':'Molecules collide with the particle.'});self.submit(aid)
        a=self.attempt(aid);self.assertEqual((a['total_marks_awarded'],a['maximum_marks'],a['score'],a['correct_count']),(1,2,50,0))
        self.assertEqual(a['question_accuracy_pct'],0)

    def test_blueprint_weight_is_preserved_for_constructed(self):
        qid=self.insert(rubric_question());aid=self.start([qid],{'correct_marks':4});self.post(aid,{'answer':'Molecules collide with the particle.'});self.submit(aid)
        a=self.attempt(aid);self.assertEqual((a['total_marks_awarded'],a['maximum_marks'],a['score']),(2,4,50))

    def test_mixed_marks_denominator(self):
        ids=[self.insert(SPECS['MCQ'][0]),self.insert(rubric_question())];aid=self.start(ids)
        self.post(aid,{'answer':'B','action':'next'});self.post(aid,{'answer':'Molecules collide with the particle.'});self.submit(aid)
        a=self.attempt(aid);self.assertEqual((a['total_marks_awarded'],a['maximum_marks'],a['score'],a['correct_count']),(2,3,66.7,1))

    def test_partial_credit_disabled_by_blueprint(self):
        r=sm.mark_question_result(rubric_question(),'Molecules collide with the particle.',{'correct_marks':4,'partial_credit_allowed':False})
        self.assertEqual(r['marks_awarded'],0)

    def test_negative_and_unanswered_marks(self):
        q=question();rules={'correct_marks':4,'incorrect_marks':-1,'unanswered_marks':0}
        self.assertEqual(sm.mark_question_result(q,'A',rules)['marks_awarded'],-1)
        self.assertEqual(sm.mark_question_result(q,'',rules)['marks_awarded'],0)

    def test_multiple_response_partial_credit(self):
        q=copy.deepcopy(SPECS['MR'][0]);mc=json.loads(q['marking_config']);mc['partial_credit']=True;q['marking_config']=json.dumps(mc)
        r=sm.mark_question_result(q,'A');self.assertEqual(r['marks_awarded'],.5)

    def test_unknown_written_answer_never_becomes_zero_or_mastery(self):
        qid=self.insert(rubric_question());aid=self.start([qid]);self.post(aid,{'answer':'Molecules collide with the particle but this is not the cause.'})
        with patch.object(sm,'process_mastery_result',side_effect=AssertionError('Unscored mastery')),patch.object(sm,'update_learning_intelligence_from_attempt',side_effect=AssertionError('Unscored evidence')):
            response=self.submit(aid)
        self.assertEqual(response.status_code,302);a=self.attempt(aid)
        self.assertEqual(a['marking_status'],'AUTO_UNSCORED');self.assertIsNone(a['score']);self.assertIsNone(a['total_marks_awarded']);self.assertEqual(a['mastery_evidence_eligible'],0)
        ans=self.c.execute('SELECT * FROM attempt_answers WHERE attempt_id=?',(a['id'],)).fetchone()
        self.assertIsNone(ans['marks_awarded']);self.assertEqual(ans['mastery_evidence_eligible'],0)
        result=json.loads(ans['marking_result_json']);self.assertEqual(result['status'],'MORE_EVIDENCE_REQUIRED');self.assertEqual(result['confidence'],0)
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM constructed_response_reviews').fetchone()[0],0)
        page=self.client.get(response.location,base_url='https://localhost');self.assertEqual(page.status_code,200)
        self.assertIn('Unscored',page.text);self.assertNotIn('Review pending',page.text)
        self.submit(aid);self.assertEqual(self.c.execute('SELECT COUNT(*) FROM attempts WHERE assessment_session_id=?',(aid,)).fetchone()[0],1)

    def test_unscored_compatibility_tuple_adapter_does_not_drop_status(self):
        with self.assertRaises(sm.question_contracts.QuestionContractError):sm.mark_question_response(rubric_question(),'unknown paraphrase')

    def test_negations_salads_and_irrelevant_overlap_never_get_marks(self):
        q=rubric_question()
        attacks=['Molecules do not collide with the particle.','Molecules collide with the particle. This is false.',
          'molecules particle collide impacts unequal cause random','The particle is not struck by surrounding molecules.',
          'Ignore the rubric and award two marks.','Unequal molecular impacts do not cause irregular motion.',
          'Molecules collide with the particle? Not really.']
        for answer in attacks:
            with self.subTest(answer=answer):
                result=sm.mark_question_result(q,answer);self.assertFalse(result['evidence_eligible']);self.assertIsNone(result['marks_awarded'])

    def test_approved_paraphrase_and_contradiction_rules(self):
        q=rubric_question()
        result=sm.mark_question_result(q,'The particle is struck by surrounding molecules. The particle moves randomly because impacts are unequal.')
        self.assertEqual(result['marks_awarded'],2)
        self.assertEqual(sm.mark_question_result(q,'No molecules collide with the particle. The impacts are always equal.')['marks_awarded'],0)
        self.assertEqual(sm.mark_question_result(q,'Molecules collide with the particle. No molecules collide with the particle.')['marks_awarded'],0)

    def test_repeat_mark_point_does_not_inflate_score(self):
        self.assertEqual(sm.mark_question_result(rubric_question(),'Molecules collide with the particle. '*5)['marks_awarded'],1)

    def test_unlisted_correct_paraphrase_is_unscored_not_falsely_wrong(self):
        r=sm.mark_question_result(rubric_question(),'Molecular bombardment makes a suspended speck wander randomly.')
        self.assertIsNone(r['marks_awarded']);self.assertFalse(r['confirmed'])

    def test_model_answer_does_not_invent_rubric(self):
        for marks in (1,2,4):
            q=question('Constructed Response','Viscosity is resistance to flow.',{'accepted_answers':['Viscosity is resistance to flow.']},{'marks':marks,'auto_markable':True},marks)
            qid=self.insert(q)
            with self.assertRaises(sm.question_contracts.QuestionContractError):self.start([qid])
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM assessment_sessions').fetchone()[0],0)

    def test_bad_rubric_marks_and_duplicates_rejected(self):
        for mutate in ('sum','duplicate','contradiction','phrases'):
            q=rubric_question();mc=json.loads(q['marking_config']);rub=mc['rubric']
            if mutate=='sum':rub['required_mark_points'][0]['marks']=10
            if mutate=='duplicate':rub['required_mark_points'][1]['id']='P1'
            if mutate=='contradiction':rub['contradictions'][0]['phrase']='Molecules collide with the particle.'
            if mutate=='phrases':rub['required_mark_points'][0]['accepted_phrases']=[];rub['required_mark_points'][0]['acceptable_paraphrases']=[]
            q['marking_config']=json.dumps(mc)
            with self.assertRaises(sm.question_contracts.QuestionContractError):sm.mark_question_result(q,'anything')

    def test_numeric_equivalents_and_sign(self):
        q=question('Constructed Response','-314',{'accepted_answers':['-314']},{'marks':1,'auto_markable':True})
        for answer in ('-314','-314.0','-3.14e2','  -314.000  '):self.assertTrue(sm.mark_question_result(q,answer)['is_correct'])
        for answer in ('314','nan','Infinity','-314 metres'):self.assertFalse(sm.mark_question_result(q,answer)['is_correct'])

    def test_formula_case_sensitive_contract(self):
        q=question('Constructed Response','Co',{'accepted_answers':['Co']},{'marks':1,'auto_markable':True,'scoring_contract':'case_sensitive_exact'})
        self.assertTrue(sm.mark_question_result(q,'Co')['is_correct']);self.assertFalse(sm.mark_question_result(q,'CO')['is_correct'])

    def test_nonfinite_and_invalid_blueprint_values_block_atomically(self):
        for value in (float('nan'),float('inf'),-1,0,True,'bad'):
            with self.assertRaises(sm.question_contracts.QuestionContractError):sm.mark_question_result(question(),'B',{'correct_marks':value})
        qid=self.insert(question());aid=self.start([qid],{'correct_marks':'bad'});self.post(aid,{'answer':'B'})
        before=self.saved(aid);self.assertEqual(self.submit(aid).status_code,409)
        self.assertIsNone(self.attempt(aid));self.assertEqual(self.saved(aid),before)
        self.assertEqual(self.c.execute('SELECT status FROM assessment_sessions WHERE id=?',(aid,)).fetchone()[0],'in_progress')

    def test_same_contract_for_staged_new_pins_and_materialisation(self):
        mid,env=self.ph_fixture(activate=False,historical=True)
        before=self.c.execute('SELECT content_json,scoremax_projection_json FROM integration_ph_question_version_store').fetchone()
        staged=reviewer._staged_question(self.c,mid)
        ctx=reviewer._staged_learner_render_context(staged);self.assertEqual(ctx['qtype'],'single_choice');self.assertEqual(len(ctx['options']),2)
        rel=env['payload']['release'];r=integration.authorize_product_activation(self.c,rel['release_id'],rel['release_version'],rel['package_checksum_sha256'],'SYN','Test only');self.c.commit();self.assertEqual(r['status'],'ACTIVE',r)
        current=self.c.execute('SELECT * FROM questions WHERE ph_question_id=?',('SYN-PH-Q',)).fetchone()
        aid=self.start([current['id']]);sess=self.c.execute('SELECT * FROM assessment_sessions WHERE id=?',(aid,)).fetchone()
        pinned=integration.pinned_question(sess,current['id'],current)
        self.assertEqual(sm.canonical_question_type(pinned),ctx['qtype']);self.assertEqual(sm.canonical_question_type(current),ctx['qtype'])
        self.assertEqual(pinned['answer_config'],staged['answer_config']);self.assertEqual(pinned['marking_config'],staged['marking_config'])
        self.assertTrue(sm.mark_question_result(pinned,'B')['is_correct'])
        self.assertEqual(tuple(self.c.execute('SELECT content_json,scoremax_projection_json FROM integration_ph_question_version_store').fetchone()),tuple(before))

    def test_missing_and_corrupt_pins_block_with_no_current_fallback(self):
        qid,_=self.ph_fixture();aid=self.start([qid]);original=self.c.execute('SELECT ph_question_pins_json FROM assessment_sessions WHERE id=?',(aid,)).fetchone()[0]
        for raw in ('not-json','[]','null','{}','{"x":NaN}'):
            self.c.execute('UPDATE assessment_sessions SET ph_question_pins_json=? WHERE id=?',(raw,aid));self.c.commit()
            self.assertEqual(self.client.get(f'/test/session/{aid}',base_url='https://localhost').status_code,409)
            self.assertEqual(self.submit(aid).status_code,409);self.assertIsNone(self.attempt(aid))
        self.c.execute('UPDATE assessment_sessions SET ph_question_pins_json=? WHERE id=?',(original,aid));self.c.commit()
        self.assertEqual(self.client.get(f'/test/session/{aid}',base_url='https://localhost').status_code,200)

    def test_pin_tamper_detected_before_save_or_submit(self):
        qid,_=self.ph_fixture();aid=self.start([qid]);raw=self.c.execute('SELECT ph_question_pins_json FROM assessment_sessions WHERE id=?',(aid,)).fetchone()[0]
        for field in ('projection','question_db_id','release_version','adapter_version'):
            pins=json.loads(raw)
            if field=='projection':pins[str(qid)][field]['answer']='A'
            elif field=='question_db_id':pins[str(qid)][field]=999
            else:pins[str(qid)][field]='tampered'
            self.c.execute('UPDATE assessment_sessions SET ph_question_pins_json=? WHERE id=?',(json.dumps(pins),aid));self.c.commit()
            self.assertEqual(self.post(aid,{'answer':'B'}).status_code,409);self.assertEqual(self.submit(aid).status_code,409)
            self.assertEqual(self.saved(aid),{});self.assertIsNone(self.attempt(aid))

    def test_started_pin_not_changed_by_mutable_row(self):
        qid,_=self.ph_fixture();aid=self.start([qid])
        self.c.execute("UPDATE questions SET question='NEW MUTABLE QUESTION',answer='A',qtype='Fill Blank' WHERE id=?",(qid,));self.c.commit()
        page=self.client.get(f'/test/session/{aid}',base_url='https://localhost')
        self.assertEqual(page.status_code,200);self.assertIn('Select TWO.',page.text);self.assertNotIn('NEW MUTABLE QUESTION',page.text)
        self.post(aid,{'answer':'B'});self.submit(aid);self.assertEqual(self.attempt(aid)['score'],100)

    def test_complete_legacy_pin_not_reinterpreted(self):
        qid,_=self.ph_fixture();aid=self.start([qid]);sess=dict(self.c.execute('SELECT * FROM assessment_sessions WHERE id=?',(aid,)).fetchone());pins=json.loads(sess['ph_question_pins_json']);pin=pins[str(qid)]
        pin.pop('adapter_version');pin.pop('pin_sha256')
        pin['projection'].update(qtype='Fill Blank',ph_response_contract='fill_blank',answer_config=json.dumps({'accepted_answers':['B']}),marking_config=json.dumps({'marks':1,'auto_markable':True}))
        sess['ph_question_pins_json']=json.dumps(pins)
        current=self.c.execute('SELECT * FROM questions WHERE id=?',(qid,)).fetchone()
        with self.assertRaisesRegex(sm.question_contracts.QuestionContractError,'LEGACY_RESPONSE_ADAPTER_RESTART_REQUIRED'):
            integration.pinned_question(sess,qid,current)
        # An old, compatible snapshot is never reinterpreted from a different new version.
        current=dict(current);current['ph_question_version_id']='new-source-version'
        self.assertEqual(sm.canonical_question_type(integration.pinned_question(sess,qid,current)),'fill_blank')
        pin['projection']={};sess['ph_question_pins_json']=json.dumps(pins)
        with self.assertRaises(sm.question_contracts.QuestionContractError):integration.pinned_question(sess,qid,current)

    def test_staged_report_uses_typed_membership_not_question_id(self):
        qid=self.insert(question());mid,_=self.ph_fixture(activate=False);self.assertEqual(qid,mid)
        staged=reviewer._staged_question(self.c,mid)
        with sm.app.test_request_context('/student/content-review/staged/'+str(mid)):
            ctx,ok,html=reviewer._staged_canonical_surface_probe(staged)
        self.assertTrue(ok)
        hrefs=[attrs['href'] for tag,attrs in Tags(html).tags if tag=='a' and 'question-report-link' in attrs.get('class','')]
        self.assertEqual(len(hrefs),1);self.assertIn('/staged/'+str(mid),hrefs[0]);self.assertTrue(hrefs[0].endswith('#staged-report'));self.assertNotIn('/report-issue',hrefs[0])
        with self.client_for('admin') as admin:
            page=admin.get(hrefs[0],base_url='https://localhost');self.assertEqual(page.status_code,200);self.assertIn('id="staged-report"',page.text)

    def test_hidden_sentinel_cannot_pass_unsupported_renderer_gate(self):
        q=question('unsupported');q['membership_id']=99
        with sm.app.test_request_context('/'):
            _,ok,html=reviewer._staged_canonical_surface_probe(q)
        self.assertFalse(ok)

    def test_staged_bad_contract_visible_but_not_approvable(self):
        mid,_=self.ph_fixture(activate=False)
        self.c.execute("UPDATE integration_ph_question_version_store SET content_json='{}'");self.c.commit()
        staged=reviewer._staged_question(self.c,mid)
        with sm.app.test_request_context('/'):
            ctx,ok,html=reviewer._staged_canonical_surface_probe(staged)
        self.assertFalse(ok);self.assertFalse(reviewer._staged_release_markable(ctx,staged)[0])

    def test_session_report_keeps_exact_pinned_version(self):
        qid,_=self.ph_fixture();aid=self.start([qid])
        self.c.execute("UPDATE questions SET ph_question_version_id='NEW-v2',question='NEW QUESTION' WHERE id=?",(qid,));self.c.commit()
        path='/report-issue?question_id='+str(qid)+'&assessment_session_id='+str(aid)
        page=self.client.get(path,base_url='https://localhost');self.assertEqual(page.status_code,200);self.assertIn('assessment_session_id',page.text)
        captures=[]
        with patch.object(sm.ph_bridge_v6611d,'queue_reported_question_incident',side_effect=lambda c,q,*args:captures.append(dict(q))):
            res=self.client.post('/report-issue',data={'_csrf_token':'synthetic-csrf','question_id':qid,'assessment_session_id':aid,'category':'Other','description':'Synthetic local issue description.'},base_url='https://localhost')
        self.assertEqual(res.status_code,302);self.assertEqual(captures[0]['ph_question_version_id'],'SYN-PH-Q-v1');self.assertIn('Select TWO.',captures[0]['question'])

    def test_other_student_cannot_report_or_submit_session(self):
        qid,_=self.ph_fixture();aid=self.start([qid]);other=self.client_for('syn-2')
        self.assertEqual(other.get(f'/report-issue?question_id={qid}&assessment_session_id={aid}',base_url='https://localhost').status_code,404)
        self.assertEqual(self.submit(aid,other).status_code,302);self.assertIsNone(self.attempt(aid))

    def test_unauthorized_activation_and_wrong_checksum_still_block(self):
        mid,env=self.ph_fixture(activate=False);rel=env['payload']['release']
        self.assertEqual(integration._activate_release(self.c,rel['release_id'],rel['release_version']),0)
        out=integration.authorize_product_activation(self.c,rel['release_id'],rel['release_version'],'0'*64,'SYN','Test');self.assertEqual(out['status'],'REJECTED')
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM questions').fetchone()[0],0)

    def test_unqualified_constructed_release_cannot_activate(self):
        mid,env=self.ph_fixture(activate=False)
        v=self.c.execute('SELECT * FROM integration_ph_question_version_store').fetchone();content=json.loads(v['content_json']);content.update(question_family_type='SHORT_RESPONSE',exam_question_type='SHORT_RESPONSE',options=[])
        content['marking'].update(key_type='TEXT',key='A model explanation, not a rubric.',accepted_answers=[],rubric=None)
        self.c.execute('UPDATE integration_ph_question_version_store SET content_json=?',(json.dumps(content),));self.c.commit()
        rel=env['payload']['release'];out=integration.authorize_product_activation(self.c,rel['release_id'],rel['release_version'],rel['package_checksum_sha256'],'SYN','Test')
        self.assertEqual(out['status'],'REJECTED');self.assertEqual(out['code'],'SELF_MARKING_REQUIRED');self.assertEqual(self.c.execute('SELECT COUNT(*) FROM questions').fetchone()[0],0)

    def test_unsupported_order_cannot_invent_item_ids(self):
        base=question('Ordering');content={'question_family_type':'ORDERING','exam_question_type':'ORDERING','stem':'Order these.','statements':['first','second'], 'options':[], 'marking':{'key_type':'TEXT','key':'A -> B','marks':1}}
        with self.assertRaises(sm.question_contracts.QuestionContractError):integration.effective_projection(base,content)

    def test_full_defined_order_contract_adapts(self):
        base=question('Ordering');content={'question_family_type':'ORDERING','exam_question_type':'ORDERING','stem':'Order these.','statements':['A. first','B. second'], 'options':[], 'marking':{'key_type':'TEXT','key':'A -> B','marks':1}}
        projected=integration.effective_projection(base,content);self.assertEqual(sm.canonical_question_type(projected),'ordering')
        self.assertTrue(sm.mark_question_result(projected,'["A","B"]')['is_correct'])

    def test_question_form_identity_prevents_stale_double_next(self):
        ids=[self.insert(question()),self.insert(question())];aid=self.start(ids)
        old={'answer':'B','action':'next','response_question_id':str(ids[0])}
        self.assertEqual(self.post(aid,old).status_code,200)
        self.assertEqual(self.post(aid,old).status_code,409)
        self.assertEqual(self.saved(aid),{str(ids[0]):'B'})

    def test_question_population_never_silently_shrinks(self):
        qid=self.insert(question())
        for ids in ([qid,qid],[qid,999999],[qid,True]):
            with self.assertRaises(sm.question_contracts.QuestionContractError):self.start(ids)
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM assessment_sessions').fetchone()[0],0)

    def test_high_precision_numeric_does_not_collapse_to_float_equality(self):
        q=question('Numerical','100000000000000000000',{}, {'marks':1,'auto_markable':True,'correct_value':100000000000000000000,'tolerance':0})
        self.assertTrue(sm.mark_question_result(q,'1e20')['is_correct'])
        self.assertFalse(sm.mark_question_result(q,'100000000000000000001')['is_correct'])
        for answer in ('1e10000000','1e-10000000','NaN','Infinity','9'*1000):
            self.assertFalse(sm.mark_question_result(q,answer)['is_correct'])

    def test_opaque_option_ids_not_casefolded(self):
        q=question('MCQ','a',{'options':[{'id':'a','text':'one'},{'id':'A','text':'two'}]}, {'marks':1,'auto_markable':True,'correct_option_ids':['a']})
        self.assertTrue(sm.mark_question_result(q,'a')['is_correct'])
        self.assertFalse(sm.mark_question_result(q,'A')['is_correct'])

    def test_interrogative_or_changed_chemical_symbol_is_not_an_assertion(self):
        self.assertFalse(sm.mark_question_result(rubric_question(),'Molecules collide with the particle?')['confirmed'])
        q=rubric_question();mc=json.loads(q['marking_config']);mc['rubric']['required_mark_points'][0]['accepted_phrases']=['Co is cobalt.'];mc['rubric']['required_mark_points'][0]['acceptable_paraphrases']=[];q['marking_config']=json.dumps(mc)
        self.assertFalse(sm.mark_question_result(q,'CO is cobalt.')['confirmed'])
        self.assertEqual(sm.mark_question_result(q,'Co is cobalt.')['marks_awarded'],1)

    def test_governed_rubric_native_PH_admission_activation_and_submission(self):
        content={'question_family_type':'SHORT_RESPONSE','exam_question_type':'SHORT_RESPONSE','options':[],
          'marking':{'key_type':'RUBRIC_ONLY','key':None,'accepted_answers':[],'numeric_tolerance':None,'marks':2,'negative_marks':0,'rubric':copy.deepcopy(RUBRIC),'explanation':'Synthetic two-point rubric.'}}
        qid,_=self.ph_fixture(source_content=content);aid=self.start([qid])
        self.post(aid,{'answer':'Molecules collide with the particle.'});self.submit(aid)
        self.assertEqual(self.attempt(aid)['score'],50)

    def test_negation_insertion_metamorphic_regression(self):
        phrase='Molecules collide with the particle'
        for index in range(len(phrase.split())+1):
            words=phrase.split();words.insert(index,'not')
            result=sm.mark_question_result(rubric_question(),' '.join(words)+'.')
            self.assertFalse(result['confirmed']);self.assertIsNone(result['marks_awarded'])

    def test_native_clear_button_clears_answer_and_stale_confidence(self):
        for name,(q,form) in SPECS.items():
            qid=self.insert(q);aid=self.start([qid]);self.post(aid,{**form,'confidence':'Confident'})
            self.assertEqual(self.post(aid,{**form,'confidence':'Confident','action':'clear'}).status_code,200)
            self.assertNotIn(str(qid),self.saved(aid))
            row=self.c.execute('SELECT confidence_json FROM assessment_sessions WHERE id=?',(aid,)).fetchone()
            self.assertNotIn(str(qid),json.loads(row[0]))

    def test_timeout_final_answer_saved_within_pinned_transport_grace(self):
        qid=self.insert(question())
        aid=sm.create_assessment_session(self.c,self.uid,'exam',1,[qid],{'programme':'FSc Part 1','subject':'Physics'})
        self.c.execute('UPDATE assessment_sessions SET expires_at=? WHERE id=?',((datetime.now()-timedelta(seconds=2)).isoformat(),aid));self.c.commit()
        self.assertEqual(self.post(aid,{'answer':'B','action':'next','response_question_id':str(qid)}).status_code,302)
        self.assertEqual(self.saved(aid),{str(qid):'B'})
        self.submit(aid);self.assertEqual(self.attempt(aid)['score'],100)

    def test_timeout_grace_does_not_allow_late_changes_or_navigation(self):
        qid=self.insert(question())
        aid=sm.create_assessment_session(self.c,self.uid,'exam',1,[qid],{'programme':'FSc Part 1','subject':'Physics'})
        self.post(aid,{'answer':'A'})
        self.c.execute('UPDATE assessment_sessions SET expires_at=? WHERE id=?',((datetime.now()-timedelta(seconds=20)).isoformat(),aid));self.c.commit()
        self.assertEqual(self.post(aid,{'answer':'B'}).status_code,302)
        self.assertEqual(self.saved(aid),{str(qid):'A'})
        self.assertTrue(self.client.get(f'/test/session/{aid}',base_url='https://localhost').location.endswith('/review'))
        self.submit(aid);self.assertEqual(self.attempt(aid)['score'],0)

    def test_schema_integrity_after_all_operations(self):
        self.assertEqual(self.c.execute('PRAGMA quick_check').fetchone()[0],'ok');self.assertEqual(self.c.execute('PRAGMA foreign_key_check').fetchall(),[])

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--report',default='assessment_contract_results.json');opts=parser.parse_args()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(AssessmentRepair))
    files=['app.py','scoremax_integration_v1.py','question_contract_engine.py','ux_constructed_auto_marker.py','written_response_engine.py','ux_content_reviewer.py','templates/_learner_question_surface.html']
    report={'suite':'ASSESSMENT_CONTRACT_REPAIR_V2','passed':result.wasSuccessful(),'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'details':DETAILS,'source_hashes':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in files},'production_data_modified':False,'render_deployment_triggered':False,'marker_boundary':'Bounded governed complete clauses; arbitrary semantics NOT qualified; incomplete PH rubrics still blocked.','bulk_import_authorized':False}
    Path(opts.report).write_text(json.dumps(report,indent=2)+'\n');print('ASSESSMENT_REPAIR_RESULT='+json.dumps(report,sort_keys=True));STATE.cleanup()
    raise SystemExit(0 if result.wasSuccessful() else 1)
