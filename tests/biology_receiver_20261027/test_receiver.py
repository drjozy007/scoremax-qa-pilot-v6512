"""Changed receiver/routing checks only. Synthetic fixtures, no PH access or releases."""
import ast,copy,hashlib,io,json,os,socket,sqlite3,sys,tempfile,time,unittest,zipfile
from datetime import datetime,timezone
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
RUNTIME=Path(sys.argv.pop(1)).resolve()
BASELINE='--baseline-probe' in sys.argv
if BASELINE:sys.argv.remove('--baseline-probe')
sys.path.insert(0,str(ROOT/'.test_deps'));sys.path.insert(0,str(RUNTIME))
WORK=Path(os.environ.get('BIOLOGY_TEST_ROOT',str(ROOT/'.test_runs/biology_receiver'))).resolve()
WORK.mkdir(parents=True,exist_ok=True)
if os.name=='nt':raise RuntimeError('Native production-startup checks require Linux; do not bypass storage validation.')
for key in tuple(os.environ):
 if key.startswith(('SCOREMAX_','POWER_HOUSE_','GROWTH_ENGINE_')):os.environ.pop(key)
os.environ.update({
 'SCOREMAX_ENV':'production','SCOREMAX_SECRET':'synthetic-biology-receiver-secret-over-32-characters',
 'SCOREMAX_STAGING_SESSION_SECRET':'synthetic-biology-receiver-staging-secret',
 'SCOREMAX_BOOTSTRAP_ADMIN_PASSWORD':'Synthetic-Biology-Only-2026',
 'SCOREMAX_BOOTSTRAP_ADMIN_EMAIL':'admin@scoremax.test',
 'SCOREMAX_PERSISTENT_ROOT':str(WORK),'SCOREMAX_DB':str(WORK/'state/scoremax.db'),
 'SCOREMAX_BACKUP_DIR':str(WORK/'backup'),'SCOREMAX_CONTENT_INTAKE_DIR':str(WORK/'intake'),
 'SCOREMAX_EXPECTED_PERSISTENT_MOUNT':'/data','WEB_CONCURRENCY':'1','SCOREMAX_INSTANCE_COUNT':'1',
 'SCOREMAX_SMTP_HOST':'smtp.invalid','SCOREMAX_SMTP_FROM':'test@scoremax.test',
 'SCOREMAX_PUBLIC_BASE_URL':'https://localhost','SCOREMAX_REQUIRE_EMAIL_VERIFICATION':'1',
 'SCOREMAX_SEND_EMAIL_VERIFICATION':'0','SCOREMAX_ENFORCE_PAYWALL':'0',
 'SCOREMAX_INTERNAL_FULL_ACCESS':'0','SCOREMAX_PUBLIC_STUDENT_OPENING':'0','SCOREMAX_INVITE_ONLY_PILOT':'0',
 'POWER_HOUSE_TO_SCOREMAX_TOKEN':'synthetic-receiver-token','POWER_HOUSE_TO_SCOREMAX_HMAC_SECRET':'synthetic-receiver-hmac',
 'SCOREMAX_PAID_AI_FEEDBACK':'0','SCOREMAX_AI_PLATFORM_BUDGET_MICRO_USD':'0'})
def deny(*a,**kw):raise RuntimeError('QUALIFICATION_NETWORK_DISABLED')
socket.socket.connect=deny;socket.socket.connect_ex=deny
sys.path.insert(0,str(ROOT/'native_guard'))
import scoremax_persistent_storage_guard as guard
assert hashlib.sha256(Path(guard.__file__).read_bytes()).hexdigest()=='c1bff2fcbe000a05aeab4401b9267dd1e460425c485aa6efc683c642fed47195'
guard.main()
import scoremax_production as hosted
sm=hosted.scoremax;app=hosted.application;integration=sm.integration_v1
import question_contract_engine as contracts
import ux_catalogue_browser as catalogue
from ux_catalogue_data import subject_items
# Reuse the accepted fixture definitions, not its historical test runner/startup.
fixture_path=ROOT/'scripts/qualify_assessment_contract_repair.py'
tree=ast.parse(fixture_path.read_text(encoding='utf8'))
nodes=[n for n in tree.body if (isinstance(n,ast.FunctionDef) and n.name in {'question','rubric_question'})
 or (isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in {'RUBRIC','SPECS'} for t in n.targets))]
fixture_ns={'copy':copy,'json':json}
exec(compile(ast.Module(body=nodes,type_ignores=[]),str(fixture_path),'exec'),fixture_ns)
SPECS=fixture_ns['SPECS']
from guided_fixture_helpers import fixture as guided_fixture
c=sm.db()
uid=c.execute("""INSERT INTO users(role,system_user_id,full_name,email,username,password_hash,account_status,
 email_verified,is_demo_account,academic_level,active_programme,subjects)
 VALUES('student','STU-999701','Synthetic Biology learner','biology@example.test','synthetic-biology',
 'not-a-real-password-hash','active',1,0,'FSc Part 1','FSc Part 1','Biology')""").lastrowid
c.commit();c.close()
SNAP=WORK/'fixture-baseline.db'
with sm.db() as source,sqlite3.connect(SNAP) as target:source.backup(target)
OBSERVATIONS=[]

class BiologyReceiverTests(unittest.TestCase):
 def setUp(self):
  self.path=WORK/(self._testMethodName+'.db')
  with sqlite3.connect(SNAP) as source,sqlite3.connect(self.path) as target:source.backup(target)
  sm.DB=self.path;os.environ['SCOREMAX_DB']=str(self.path)
  self.c=sm.db();self.client=app.test_client()
  with self.client.session_transaction(base_url='https://localhost') as state:
   state.update(user_id=uid,role='student',session_version=0,_csrf_token='synthetic-csrf')
  self.counter=0
 def tearDown(self):
  self.c.rollback();self.c.close()
  assert self.path.parent==WORK
  self.path.unlink(missing_ok=True)
 def programme(self,value):
  self.c.execute('UPDATE users SET active_programme=? WHERE id=?',(value,uid));self.c.commit()
 def local(self,kind,programme='FSc Part 1',chapter=None,section='SYN-SECTION-A',topic='Shared topic'):
  q=copy.deepcopy(SPECS[kind][0]);self.counter+=1
  item=subject_items('year12' if programme=='FSc Part 2' else 'year11','Biology')[0]
  q.update(question_id='SYN-LOCAL-'+str(self.counter),family_id='SYN-FAMILY-'+str(self.counter),
   programme=programme,qualification=programme,subject='Biology',chapter=chapter or item['name'],topic=topic,
   level='Foundation',difficulty='Foundation',status='Approved',review_status='Approved',active=1,is_demo=0,
   scoremax_ready=1,ph_projection_owner='',source_type='ISOLATED_SYNTHETIC_TEST',rights_status='ScoreMax Original',
   content_environment='PRODUCTION',country='Pakistan',family_key='SYN-FAMILY-'+str(self.counter),
   ph_curriculum_snapshot_json=json.dumps({'section_id':section,'display':{'section':'Existing section '+section}}))
  q['family_key']=sm.upsert_question_family(self.c,q,review_status='Approved',active=1)
  columns={r[1] for r in self.c.execute('PRAGMA table_info(questions)')};q={k:v for k,v in q.items() if k in columns}
  result=self.c.execute('INSERT INTO questions('+','.join(q)+') VALUES('+','.join('?' for _ in q)+')',tuple(q.values())).lastrowid
  self.c.commit();return result
 def envelope(self,label='one',year=11,chapter_index=0,question=None):
  env=json.loads((RUNTIME/'integration_examples/PH_SM_APPROVED_CONTENT_V1.example.json').read_text())
  item=subject_items('year11' if year==11 else 'year12','Biology')[chapter_index]
  now=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
  rel=env['payload']['release'];q=copy.deepcopy(question or env['payload']['questions'][0])
  opaque='SYN-OPAQUE-CHAPTER-'+str(year)+'-'+str(chapter_index)
  rel.update(release_id='SYN-BIO-'+label,release_version='1',programme_id='FSC_PART_I' if year==11 else 'FSC_PART_II',
   subject_id='BIOLOGY',chapter_id=opaque,generated_at=now,effective_at=now)
  if question is None:
   q.update(question_id='SYN-BIO-Q-'+label,question_version_id='SYN-BIO-QV-'+label+'-1',question_version_number=1,supersedes_question_version_id=None)
   q['curriculum'].update(programme_id=rel['programme_id'],subject_id='BIOLOGY',chapter_id=opaque,grade_year_id='YEAR_'+str(year),section_id='SYN-SECTION-A')
   q['curriculum']['display'].update(programme='FSc Part 1' if year==11 else 'FSc Part 2',grade_year='Year '+str(year),
    subject='Biology',chapter_number=item['number'],chapter=item['name'],section='Governed section A',topic='Governed topic')
   q['content']['stem']='[SYNTHETIC] Choose the existing fixture answer.'
   q['architecture']['claim_family_id']='SYN-FAMILY-'+label
   q['question_checksum_sha256']=integration._object_checksum(q,'question_checksum_sha256')
  env.update(message_id='SYN-MSG-'+label,idempotency_key='SYN-IDEM-'+label,occurred_at=now,sent_at=now)
  env['payload']['questions']=[q];env['payload_checksum_sha256']=integration.payload_checksum(env['payload'])
  return env
 def admit(self,env,activate=True):
  rec,status=integration.admit_content_envelope(self.c,env,env['payload_checksum_sha256'])
  self.assertEqual(status,202,rec)
  if activate:
   r=env['payload']['release'];answer=integration.authorize_product_activation(self.c,r['release_id'],r['release_version'],r['package_checksum_sha256'],'SYNTHETIC-OWNER','Disposable Biology receiver check')
   self.assertEqual(answer['status'],'ACTIVE',answer);self.c.commit()
  return rec
 def request_start(self,**values):
  form={'subject':'Biology','programme':'FSc Part 1','scope':'full','count':'2','mode':'practice','_csrf_token':'synthetic-csrf'}
  form.update(values)
  return self.client.post('/test/start',data=form,base_url='https://localhost')
 def session_for(self,response):
  self.assertEqual(response.status_code,302,response.text[:200])
  row=self.c.execute('SELECT * FROM assessment_sessions WHERE student_id=? ORDER BY id DESC LIMIT 1',(uid,)).fetchone()
  self.assertIsNotNone(row,{'redirect':response.location,'message':response.text[:300]})
  return row

 def test_opaque_governed_chapters_and_both_school_years(self):
  for year in (11,12):
   env=self.envelope('school-'+str(year),year)
   self.admit(env)
   result=catalogue._release_scope_counts(self.c,'year11' if year==11 else 'year12','Biology')
   item=subject_items('year11' if year==11 else 'year12','Biology')[0]
   match=catalogue._catalogue_item_scope(result,item)
   if BASELINE:self.assertIsNone(match)
   else:self.assertEqual(match['count'],1);self.assertEqual(match['chapter'],item['name'])
  OBSERVATIONS.append({'opaque_governed_chapter_mapping':not BASELINE})

 def test_question_format_is_filtered_before_sampling(self):
  expected=self.local('TF')
  for _ in range(4):self.local('MCQ')
  session=self.session_for(self.request_start(question_type='true_false'))
  ids=[int(v) for v in session['question_ids'].split(',')]
  if BASELINE:self.assertEqual(len(ids),2);self.assertNotEqual(ids,[expected])
  else:self.assertEqual(ids,[expected])

 def test_all_eight_formats_use_existing_contract_interpreter(self):
  for kind,(q,_) in SPECS.items():
   qid=self.local(kind);actual=sm.canonical_question_type(q)
   if BASELINE:continue
   sql,args=sm.practice_type_scope(actual)
   matches={r[0] for r in self.c.execute('SELECT q.id FROM questions q WHERE '+sql,args)}
   self.assertIn(qid,matches)
   for other in matches:
    row=self.c.execute('SELECT * FROM questions WHERE id=?',(other,)).fetchone()
    self.assertEqual(sm.canonical_question_type(row),actual)

 def test_topic_selection_remains_in_chapter_and_section(self):
  chapter=subject_items('year11','Biology')[0]['name']
  desired=self.local('MCQ',chapter=chapter,section='SYN-SECTION-A')
  self.local('MCQ',chapter=chapter,section='SYN-SECTION-B')
  self.local('MCQ',chapter=subject_items('year11','Biology')[1]['name'],section='SYN-SECTION-A')
  session=self.session_for(self.request_start(scope='topic',chapter=chapter,section='SYN-SECTION-A',topic='Shared topic',count='3'))
  ids=[int(v) for v in session['question_ids'].split(',')]
  if BASELINE:self.assertEqual(len(ids),3)
  else:
   self.assertEqual(ids,[desired]);meta=json.loads(session['meta_json']);self.assertEqual(meta['chapters'],chapter);self.assertEqual(meta['section'],'SYN-SECTION-A')

 def test_mdcat_practice_and_mcq_only_mock_boundary(self):
  tf=self.local('TF',programme='MDCAT');self.programme('MDCAT')
  self.assertTrue(sm.create_assessment_session(self.c,uid,'practice',None,[tf],{'programme':'MDCAT','subject':'Biology'}))
  if BASELINE:
   self.assertTrue(sm.create_assessment_session(self.c,uid,'mock',10,[tf],{'programme':'MDCAT','subject':'Biology'}))
  else:
   with self.assertRaisesRegex(contracts.QuestionContractError,'MDCAT_EXAM_MCQS_ONLY'):
    sm.create_assessment_session(self.c,uid,'mock',10,[tf],{'programme':'MDCAT','subject':'Biology'})
   self.assertEqual(self.request_start(programme='MDCAT',mode='mock',question_type='true_false').status_code,409)
   mcq=self.local('MCQ',programme='MDCAT')
   session=self.session_for(self.request_start(programme='MDCAT',mode='mock'))
   self.assertEqual(session['question_ids'],str(mcq))

 def test_signed_admission_and_accepted_replay_skip_compilation(self):
  env=self.envelope('signed')
  path='/api/integration/v1/power-house/content-releases';sent=env['sent_at'];sha=env['payload_checksum_sha256']
  headers={'Authorization':'Bearer synthetic-receiver-token','X-Message-Id':env['message_id'],'X-Sent-At':sent,'X-Content-SHA256':sha,
   'X-Signature':'hmac-sha256='+integration.signature('POST',path,env['message_id'],sent,sha,'synthetic-receiver-hmac')}
  bad=self.client.post(path,json=env,headers=dict(headers,Authorization='Bearer wrong'),base_url='https://localhost')
  self.assertEqual(bad.status_code,401)
  first=self.client.post(path,json=env,headers=headers,base_url='https://localhost')
  self.assertEqual(first.status_code,202,first.text[:500])
  with patch.object(integration,'_projection',wraps=integration._projection) as compile_projection:
   replay=self.client.post(path,json=env,headers=headers,base_url='https://localhost')
   self.assertEqual(replay.status_code,200)
   self.assertEqual(compile_projection.call_count,0 if not BASELINE else 1)
  self.assertEqual(self.c.execute('SELECT count(*) FROM integration_ph_question_version_store').fetchone()[0],1)
  self.assertEqual(self.c.execute('SELECT count(*) FROM questions WHERE ph_projection_owner=\'POWER_HOUSE\'').fetchone()[0],0)

 def test_shared_crosswalk_is_one_canonical_question_and_distinct_counts(self):
  env=self.envelope('shared');self.admit(env)
  other=self.envelope('overlap',question=env['payload']['questions'][0]);self.admit(other)
  md=self.envelope('mdcat',question=env['payload']['questions'][0])
  md['payload']['release'].update(programme_id='MDCAT',chapter_id='MDCAT::BIOLOGY::UNIT::01')
  md['payload_checksum_sha256']=integration.payload_checksum(md['payload']);self.admit(md)
  self.assertEqual(self.c.execute("SELECT count(*) FROM questions WHERE ph_projection_owner='POWER_HOUSE'").fetchone()[0],1)
  self.assertEqual(self.c.execute('SELECT count(*) FROM integration_ph_question_version_store').fetchone()[0],1)
  if not BASELINE:
   fsc=catalogue._release_scope_counts(self.c,'year11','Biology')
   self.assertEqual(next(iter(fsc.values()))['count'],1)
   mdcat=catalogue._release_scope_counts(self.c,'mdcat','Biology')
   self.assertEqual(next(iter(mdcat.values()))['count'],1)

 def test_new_versions_do_not_rewrite_saved_original_answers_or_results(self):
  env=self.envelope('history');self.admit(env)
  qid=self.c.execute("SELECT id FROM questions WHERE ph_question_id=?",(env['payload']['questions'][0]['question_id'],)).fetchone()[0]
  aid=sm.create_assessment_session(self.c,uid,'practice',None,[qid],{'programme':'FSc Part 1','subject':'Biology'})
  self.client.post('/test/session/'+str(aid),data={'_csrf_token':'synthetic-csrf','response_present':'1','answer':'B','action':'review'},base_url='https://localhost')
  new=copy.deepcopy(env);r=new['payload']['release'];r.update(release_version='2',supersedes_release_version='1')
  q=new['payload']['questions'][0];q.update(question_version_id=q['question_version_id']+'-new',question_version_number=2,supersedes_question_version_id=q['question_version_id'])
  q['content']['marking']['key']='A';q['question_checksum_sha256']=integration._object_checksum(q,'question_checksum_sha256')
  new.update(message_id='SYN-MSG-HISTORY2',idempotency_key='SYN-IDEM-HISTORY2')
  new['payload_checksum_sha256']=integration.payload_checksum(new['payload']);self.admit(new)
  self.assertEqual(self.client.get('/test/session/'+str(aid),base_url='https://localhost').status_code,200)
  reply=self.client.post('/test/session/'+str(aid)+'/submit',data={'_csrf_token':'synthetic-csrf'},base_url='https://localhost')
  if BASELINE:
   self.assertEqual(reply.status_code,409);return
  self.assertEqual(reply.status_code,302,reply.text[:300])
  attempt=self.c.execute('SELECT * FROM attempts WHERE assessment_session_id=?',(aid,)).fetchone()
  self.assertEqual(attempt['score'],100)
  answer=self.c.execute('SELECT * FROM attempt_answers WHERE attempt_id=?',(attempt['id'],)).fetchone()
  self.assertEqual(answer['ph_question_version_id'],env['payload']['questions'][0]['question_version_id'])
  self.assertEqual(self.client.get(reply.location,base_url='https://localhost').status_code,200)

 def test_unsupported_package_is_held_without_poisoning_next_approved_batch(self):
  bad=self.envelope('unsupported')
  bad['payload']['questions'][0]['content']['marking']['key_type']='RUBRIC_ONLY'
  bad['payload']['questions'][0]['content']['options']=[]
  bad['payload']['questions'][0]['content']['marking']['rubric']={}
  bad['payload']['questions'][0]['content']['question_family_type']='CONSTRUCTED_RESPONSE'
  bad['payload']['questions'][0]['content']['exam_question_type']='SHORT_RESPONSE'
  q=bad['payload']['questions'][0];q['question_checksum_sha256']=integration._object_checksum(q,'question_checksum_sha256')
  bad['payload_checksum_sha256']=integration.payload_checksum(bad['payload'])
  receipt,status=integration.admit_content_envelope(self.c,bad,bad['payload_checksum_sha256'])
  self.assertEqual(status,422,receipt)
  self.assertEqual(self.c.execute("SELECT count(*) FROM integration_ph_content_releases").fetchone()[0],0)
  self.admit(self.envelope('supported-after-held'))
  self.assertEqual(self.c.execute("SELECT count(*) FROM questions WHERE ph_projection_owner='POWER_HOUSE'").fetchone()[0],1)

 def test_release_withdrawal_preserves_other_authorized_placement_only(self):
  env=self.envelope('keep-fsc');self.admit(env)
  md=self.envelope('withdraw-md',question=env['payload']['questions'][0])
  md['payload']['release'].update(programme_id='MDCAT',chapter_id='MDCAT::BIOLOGY::UNIT::01')
  md['payload_checksum_sha256']=integration.payload_checksum(md['payload']);self.admit(md)
  stop=copy.deepcopy(md);r=stop['payload']['release'];r.update(release_version='STOP',supersedes_release_version='1',withdrawn_at=integration.utcnow(),withdrawal_reason='Synthetic placement-only stop')
  stop['payload'].update(questions=[],stimuli=[]);r.update(question_count=0,stimulus_count=0)
  integration._withdraw_release(self.c,stop,'SYNTHETIC-SEMANTIC');self.c.commit()
  row=self.c.execute("SELECT * FROM questions WHERE ph_projection_owner='POWER_HOUSE'").fetchone()
  self.assertEqual(row['active'],0 if BASELINE else 1)
  if not BASELINE:
   self.assertEqual(row['ph_release_id'],env['payload']['release']['release_id'])
   self.assertEqual(catalogue._release_scope_counts(self.c,'mdcat','Biology'),{})
   self.assertEqual(next(iter(catalogue._release_scope_counts(self.c,'year11','Biology').values()))['count'],1)

 def test_prior_academic_question_withdrawal_is_not_reactivated(self):
  env=self.envelope('academic-stop');self.admit(env)
  md=self.envelope('academic-md',question=env['payload']['questions'][0]);md['payload']['release'].update(programme_id='MDCAT',chapter_id='MDCAT::BIOLOGY::UNIT::01')
  md['payload_checksum_sha256']=integration.payload_checksum(md['payload']);self.admit(md)
  self.c.execute("UPDATE questions SET active=0,status='Withdrawn' WHERE ph_projection_owner='POWER_HOUSE'");self.c.commit()
  stop=copy.deepcopy(md);stop['payload']['release'].update(release_version='STOP',supersedes_release_version='1')
  integration._withdraw_release(self.c,stop,'SYN');self.c.commit()
  self.assertEqual(self.c.execute("SELECT active FROM questions WHERE ph_projection_owner='POWER_HOUSE'").fetchone()[0],0)

 def test_reverse_membership_lookup_uses_covering_index(self):
  plan=' '.join(str(row[3]) for row in self.c.execute("EXPLAIN QUERY PLAN SELECT release_id,release_version FROM integration_ph_release_question_membership WHERE question_id=? AND question_version_id=?",('SYN-Q','SYN-V')))
  if BASELINE:self.assertNotIn('idx_ph_membership_question_version',plan)
  else:self.assertIn('idx_ph_membership_question_version',plan);self.assertIn('SEARCH',plan)

 def test_native_chapter_navigation_counts_sections_and_existing_mobile_layout(self):
  env=self.envelope('navigation');self.admit(env)
  chapter=subject_items('year11','Biology')[0]['name']
  page=self.client.get('/student/catalogue/year11/Biology',base_url='https://localhost')
  self.assertEqual(page.status_code,200)
  if not BASELINE:
   self.assertIn('1 question available',page.text)
   chapter_page=self.client.get('/student/chapter',query_string={'subject':'Biology','chapter':chapter},base_url='https://localhost')
   self.assertEqual(chapter_page.status_code,200,chapter_page.text[:200])
   self.assertIn('Governed section A',chapter_page.text);self.assertIn('1 scored practice questions',chapter_page.text)
   setup=self.client.get('/test/setup',query_string={'subject':'Biology','chapter':chapter,'scope':'chapter'},base_url='https://localhost')
   self.assertEqual(setup.status_code,200);self.assertIn('name="question_type"',setup.text);self.assertIn('name="section"',setup.text)
  self.assertIn('@media(max-width:600px)',page.text)


 def test_guided_only_chapter_uses_existing_unscored_practice(self):
  import guided_self_assessment as guided
  runtime_q=guided_fixture();env=self.envelope('guided-only')
  q=env['payload']['questions'][0];q['content'].update(
   question_family_type='CONSTRUCTED_RESPONSE',exam_question_type='SHORT_RESPONSE',
   stem=runtime_q['question'],options=[],statements=[],command_word='describe',
   marking={'key_type':'RUBRIC_ONLY','key':runtime_q['answer'],'accepted_answers':[],
    'numeric_tolerance':None,'marks':3,'negative_marks':0,
    'rubric':json.loads(runtime_q['marking_config'])['rubric'],'explanation':'Synthetic guided example.'})
  q['architecture'].update(independent_mastery_eligible=False,independent_mastery_weight=0)
  q['question_checksum_sha256']=integration._object_checksum(q,'question_checksum_sha256')
  env['payload_checksum_sha256']=integration.payload_checksum(env['payload']);self.admit(env)
  if BASELINE:return
  chapter=subject_items('year11','Biology')[0]['name']
  scope=next(iter(catalogue._release_scope_counts(self.c,'year11','Biology').values()))
  self.assertEqual((scope['scored_count'],scope['guided_count']),(0,1))
  page=self.client.get('/student/catalogue/year11/Biology',base_url='https://localhost')
  self.assertIn('guided practice, no score',page.text)
  self.assertIn('response_mode=GUIDED_SELF_ASSESSMENT',page.text)
  response=self.request_start(response_mode=guided.MODE,scope='chapter',chapter=chapter,count='1')
  assessment=self.session_for(response);aid=assessment['id']
  self.assertEqual(self.client.get('/test/session/'+str(aid),base_url='https://localhost').status_code,200)
  saved=self.client.post('/test/session/'+str(aid),data={'_csrf_token':'synthetic-csrf','response_present':'1',
       'answer':'[SYNTHETIC] saved guided response','action':'review'},base_url='https://localhost')
  self.assertIn(saved.status_code,(200,302))
  with patch.object(sm,'mark_question_result',side_effect=AssertionError('Guided practice must not be scored')):
   submitted=self.client.post('/test/session/'+str(aid)+'/submit',data={'_csrf_token':'synthetic-csrf'},base_url='https://localhost')
  self.assertEqual(submitted.status_code,302)
  self.assertEqual(self.c.execute('SELECT count(*) FROM attempts WHERE assessment_session_id=?',(aid,)).fetchone()[0],0)

 def test_withdrawn_release_cannot_use_superseded_session_fallback(self):
  env=self.envelope('withdraw-session');self.admit(env)
  qid=self.c.execute('SELECT id FROM questions WHERE ph_question_id=?',(env['payload']['questions'][0]['question_id'],)).fetchone()[0]
  aid=sm.create_assessment_session(self.c,uid,'practice',None,[qid],{'programme':'FSc Part 1','subject':'Biology'})
  self.c.execute("UPDATE integration_ph_content_releases SET local_status='WITHDRAWN' WHERE release_id=?",(env['payload']['release']['release_id'],));self.c.commit()
  reply=self.client.post('/test/session/'+str(aid)+'/submit',data={'_csrf_token':'synthetic-csrf'},base_url='https://localhost')
  self.assertEqual(reply.status_code,409)
  self.assertEqual(self.c.execute('SELECT count(*) FROM attempts WHERE assessment_session_id=?',(aid,)).fetchone()[0],0)

if __name__=='__main__':
 suite=unittest.defaultTestLoader.loadTestsFromTestCase(BiologyReceiverTests)
 outcome=unittest.TextTestRunner(verbosity=2).run(suite)
 summary={'status':'BASELINE_GAPS_REPRODUCED' if BASELINE else 'BIOLOGY_RECEIVER_CHANGED_PATHS_PASS',
  'tests':outcome.testsRun,'failures':len(outcome.failures),'errors':len(outcome.errors),
  'production_data_used':False,'power_house_accessed':False,'historical_transfers_or_acks_replayed':False,
  'academic_banks_generated':False,'paid_AI_calls':0,'live_activation':False}
 print('BIOLOGY_RECEIVER_RESULT='+json.dumps(summary))
 sys.exit(0 if outcome.wasSuccessful() else 1)
