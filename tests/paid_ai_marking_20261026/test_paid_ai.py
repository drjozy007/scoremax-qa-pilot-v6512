"""Synthetic engineering tests, never independently approved reference marking."""
import copy,importlib.util,json,sqlite3,sys,tempfile,threading,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.test_deps'))
RUNTIME=Path(sys.argv.pop(1)) if len(sys.argv)>1 else ROOT/'scoremax_runtime_v669b'
sys.path.insert(0,str(RUNTIME))
spec=importlib.util.spec_from_file_location('paid_ai',ROOT/'ux_vnext_overlay/paid_ai_marking_20261026/paid_ai_marking.py')
ai=importlib.util.module_from_spec(spec);spec.loader.exec_module(ai)

PAID={'access_rank':1,'source':'provider','subscription':{'status':'active','price_minor':999}}
ENV={'SCOREMAX_PAID_AI_FEEDBACK':'1','DEEPSEEK_API_KEY':'synthetic-never-sent','SCOREMAX_AI_PLATFORM_BUDGET_MICRO_USD':'1000000'}
RUBRIC={'version':'PH-SAQ-SCORING-CONTRACT-1','maximum_marks':2,'auto_marking_eligibility':'DETERMINISTICALLY_SCORABLE','scoring_type':'EXACT_BOUNDED',
 'required_mark_points':[{'id':'P1','marks':1,'description':'First approved point','accepted_expressions':['x']},
                         {'id':'P2','marks':1,'description':'Second approved point','accepted_expressions':['y']}]}
Q={'qtype':'constructed_response','question':'State the two synthetic symbols.','answer':'x and y','marks':2,
   'answer_config':json.dumps({'scoring_contract':'governed_clause_rubric_v1'}),
   'marking_config':json.dumps({'marks':2,'auto_markable':True,'scoring_contract':'governed_clause_rubric_v1','rubric':RUBRIC})}
VALID={'total_marks':1,'points':[{'id':'P1','awarded':1,'correct_elements':['First point supplied'],'mistakes':[]},
                              {'id':'P2','awarded':0,'correct_elements':[],'mistakes':['Second point omitted']}],
       'improvement':'Include the second approved point.'}

class PaidAITests(unittest.TestCase):
 def setUp(self):
  root=(ROOT/'.test_runs').resolve();assert root.is_relative_to(ROOT.resolve()) and not root.is_symlink();root.mkdir(exist_ok=True)
  self.work=tempfile.TemporaryDirectory(dir=root);self.path=Path(self.work.name)/'synthetic.sqlite3'
  self.c=self.connect();self.c.executescript('CREATE TABLE users(id INTEGER PRIMARY KEY);CREATE TABLE attempts(id INTEGER PRIMARY KEY,score REAL);CREATE TABLE questions(id INTEGER PRIMARY KEY);INSERT INTO users VALUES(1);INSERT INTO users VALUES(2);INSERT INTO attempts VALUES(1,55);INSERT INTO questions VALUES(1);')
  ai.schema(self.c);self.calls=0
 def tearDown(self):self.c.close();self.work.cleanup()
 def connect(self):c=sqlite3.connect(self.path,timeout=5);c.execute('PRAGMA foreign_keys=ON');return c
 def provider(self,messages,key):
  self.calls+=1;self.assertNotIn('student_id',json.dumps(messages));self.assertLessEqual(sum(len(m['content'].encode()) for m in messages)+128,16384);return copy.deepcopy(VALID)
 def request(self,**override):
  values=dict(student_id=1,attempt_id=1,question_db_id=1,version='SYNTHETIC-V1',profile=PAID,q=Q,response='x',
              environ=ENV,provider=self.provider,now='2026-10-26T16:00:00Z')
  values.update(override);return ai.feedback(self.c,**values)
 def assert_code(self,code,**kw):
  with self.assertRaises(ai.FeedbackError) as cm:self.request(**kw)
  self.assertEqual(cm.exception.code,code)
 def test_free_trial_and_unpaid_override_make_no_provider_call(self):
  for p in [{'access_rank':0,'source':'free'}, {'access_rank':1,'source':'provider','subscription':{'status':'trial','price_minor':999}},
            {'access_rank':4,'source':'admin_override'}]:
   self.assert_code('ACTIVE_PAID_ENTITLEMENT_REQUIRED',profile=p)
  self.assertEqual(self.calls,0)
 def test_missing_key_zero_or_invalid_budget_disable_safely(self):
  for e in [{},dict(ENV,DEEPSEEK_API_KEY=''),dict(ENV,SCOREMAX_AI_PLATFORM_BUDGET_MICRO_USD='0'),dict(ENV,SCOREMAX_AI_PLATFORM_BUDGET_MICRO_USD='bad')]:
   self.assertFalse(ai.configured(e));self.assert_code('PAID_AI_NOT_CONFIGURED',environ=e)
  self.assertEqual(self.calls,0)
 def test_one_structured_reply_has_source_answer_missing_points_and_no_official_change(self):
  out=self.request();self.assertEqual(out['approved_answer'],'x and y');self.assertEqual(out['missing_marking_points'],['P2'])
  self.assertEqual(out['approved_alternatives'],['x','y']);self.assertFalse(out['official_score_or_mastery_changed'])
  self.assertEqual(self.c.execute('SELECT score FROM attempts').fetchone()[0],55)
  self.assertEqual(self.calls,1)
 def test_repeat_is_persistent_cached_result_without_new_charge_or_call(self):
  first=self.request();second=self.request();self.assertEqual(first,second);self.assertEqual(self.calls,1)
  self.assertEqual(self.c.execute('SELECT sum(reserved_micro_usd),count(*) FROM paid_ai_feedback_requests').fetchone(),(5837,1))
 def test_platform_budget_denies_before_dispatch(self):
  self.assert_code('AI_PLATFORM_BUDGET_EXHAUSTED',environ=dict(ENV,SCOREMAX_AI_PLATFORM_BUDGET_MICRO_USD='5836'))
  self.assertEqual(self.calls,0)
 def test_unknown_timeout_holds_budget_and_never_retries(self):
  def timeout(*args):self.calls+=1;raise TimeoutError()
  self.assert_code('AI_PROVIDER_OUTCOME_UNCERTAIN',provider=timeout)
  self.assert_code('AI_REQUEST_ALREADY_RESERVED_DO_NOT_RETRY',provider=timeout)
  self.assert_code('AI_PROVIDER_REQUEST_IN_PROGRESS',provider=timeout,response='y')
  self.assertEqual(self.calls,1)
  self.assertEqual(self.c.execute('SELECT state,reserved_micro_usd FROM paid_ai_feedback_requests').fetchone(),('UNCERTAIN',5837))
 def test_unknown_points_fractional_overmarks_nan_and_mismatched_totals_are_rejected(self):
  packet=ai.packet_from_native(Q,'x')[0]
  samples=[]
  v=copy.deepcopy(VALID);v['points'][0]['id']='INVENTED';samples.append(v)
  v=copy.deepcopy(VALID);v['points'][0]['awarded']=2;v['total_marks']=2;samples.append(v)
  v=copy.deepcopy(VALID);v['points'][0]['awarded']=0.5;v['total_marks']=0.5;samples.append(v)
  v=copy.deepcopy(VALID);v['points'][0]['awarded']=float('nan');samples.append(v)
  v=copy.deepcopy(VALID);v['total_marks']=2;samples.append(v)
  for v in samples:
   with self.assertRaises(ai.FeedbackError):ai.validate_feedback(v,packet)
 def test_input_contact_details_and_oversize_rubrics_are_not_sent(self):
  for response in ['name@example.test','STU-123456','+44 7700 900123','x'*20000]:
   with self.assertRaises(ai.FeedbackError):self.request(response=response)
  self.assertEqual(self.calls,0)
 def test_guided_or_ungoverned_rubric_is_not_promoted_to_scored_ai(self):
  q=copy.deepcopy(Q);q['marking_config']=json.dumps({'marks':2,'auto_markable':True,'scoring_contract':'governed_clause_rubric_v1','rubric':dict(RUBRIC,version='UNAPPROVED')})
  with self.assertRaises((ai.FeedbackError,ValueError)):self.request(q=q)
  self.assertEqual(self.calls,0)
 def test_daily_and_monthly_member_quotas_are_checked_before_dispatch(self):
  def add_fake(n,stamp):
   self.c.execute("""INSERT INTO paid_ai_feedback_requests
      (request_key,student_id,attempt_id,question_db_id,question_version_id,rubric_sha256,response_sha256,provider_model,policy,created_at,state,reserved_micro_usd)
      VALUES(?,1,1,1,'V','R',?,'model','policy',?,'COMPLETE',1)""",(str(n),str(n),stamp))
  for n in range(20):add_fake(n,'2026-10-26T12:00:00Z')
  self.c.commit();self.assert_code('AI_MEMBER_QUOTA_EXHAUSTED')
  self.c.execute('DELETE FROM paid_ai_feedback_requests')
  for n in range(200):add_fake(n,'2026-10-01T12:00:00Z')
  self.c.commit();self.assert_code('AI_MEMBER_QUOTA_EXHAUSTED');self.assertEqual(self.calls,0)
 def test_cross_connection_last_budget_cannot_be_double_reserved(self):
  c2=self.connect();errors=[];keys=[];start=threading.Barrier(2)
  def reserve_one(index):
   c=self.connect()
   try:
    start.wait();keys.append(ai.reserve(c,student_id=index,attempt_id=1,question_db_id=1,version='V',rubric_hash='R',response_hash=str(index),cap=5837,now='2026-10-26T16:00:00Z')[0])
   except ai.FeedbackError as e:errors.append(e.code)
   finally:c.close()
  threads=[threading.Thread(target=reserve_one,args=(i,)) for i in (1,2)]
  for t in threads:t.start()
  for t in threads:t.join(10)
  self.assertEqual(len(keys),1);self.assertEqual(errors,['AI_PLATFORM_BUDGET_EXHAUSTED'])
  self.assertEqual(c2.execute('SELECT sum(reserved_micro_usd) FROM paid_ai_feedback_requests').fetchone()[0],5837);c2.close()
 def test_provider_redirects_are_rejected(self):
  with self.assertRaises(ai.FeedbackError):ai.NoRedirect().redirect_request(None,None,None,None,None,None)


 def install_fixture(self):
  import types
  from flask import Flask
  from jinja2 import ChoiceLoader,DictLoader,FileSystemLoader
  self.c.executescript("""
   ALTER TABLE users ADD COLUMN full_name TEXT DEFAULT 'Synthetic learner';
   ALTER TABLE users ADD COLUMN email TEXT DEFAULT 'synthetic@example.test';
   ALTER TABLE users ADD COLUMN system_user_id TEXT DEFAULT 'STU-999901';
   ALTER TABLE attempts ADD COLUMN student_id INTEGER;
   ALTER TABLE attempts ADD COLUMN assessment_session_id INTEGER;
   UPDATE attempts SET student_id=1,assessment_session_id=1;
   ALTER TABLE questions ADD COLUMN active INTEGER DEFAULT 1;
   CREATE TABLE assessment_sessions(id INTEGER PRIMARY KEY,student_id,status);
   INSERT INTO assessment_sessions VALUES(1,1,'submitted');
   CREATE TABLE attempt_answers(attempt_id,question_db_id,selected_answer,ph_question_id,ph_question_version_id,
     ph_question_checksum_sha256,ph_release_id,ph_release_version,ph_release_checksum_sha256);
   INSERT INTO attempt_answers VALUES(1,1,'x','Q','V','H','R','1','C');
   CREATE TABLE integration_ph_content_releases(release_id,release_version,package_checksum_sha256,local_status);
   INSERT INTO integration_ph_content_releases VALUES('R','1','C','ACTIVE');
   CREATE TABLE integration_ph_product_activation_authorizations(release_id,release_version,package_checksum_sha256,activation_status);
   INSERT INTO integration_ph_product_activation_authorizations VALUES('R','1','C','ACTIVATED');
   CREATE TABLE ph_bridge_staged_withdrawal_exclusions_v6611e(release_id,release_version,question_id,question_version_id);
  """)
  self.c.commit()
  app=Flask(__name__);app.secret_key='synthetic-fixture-key'
  app.jinja_loader=ChoiceLoader([FileSystemLoader(str(ROOT/'ux_vnext_overlay/paid_ai_marking_20261026')),
      DictLoader({'base.html':'{% block content %}{% endblock %}'})])
  app.jinja_env.globals['csrf_token']=lambda:'synthetic-csrf'
  app.add_url_rule('/result/<int:aid>','result',lambda aid:'result')
  pin=dict(question_id='Q',question_version_id='V',question_checksum_sha256='H',release_id='R',release_version='1',release_checksum_sha256='C')
  def database():
   c=self.connect();c.row_factory=sqlite3.Row;return c
  native=types.SimpleNamespace(app=app,db=database,require=lambda role:True,get_access_profile=lambda c,uid:PAID,
    live_question_clause=lambda alias:alias+'.active=1',
    get_assessment_session=lambda c,aid,uid:c.execute('SELECT * FROM assessment_sessions WHERE id=? AND student_id=?',(aid,uid)).fetchone(),
    integration_v1=types.SimpleNamespace(answer_pin=lambda assessment,qid:pin,pinned_question=lambda a,qid,current:Q),
    mark_question_result=lambda q,response:{'confirmed':False})
  ai.install(native)
  return app,native
 def test_owned_snapshot_loader_rejects_cross_student_and_changed_pin(self):
  app,native=self.install_fixture();c=native.db()
  try:
   material=app.extensions['scoremax_paid_ai_owned_material']
   with self.assertRaises(ai.FeedbackError) as cm:material(c,1,1,2)
   self.assertEqual(cm.exception.code,'ASSESSMENT_NOT_FOUND')
   self.assertEqual(material(c,1,1,1)[2]['question_version_id'],'V')
   c.execute("UPDATE attempt_answers SET ph_question_version_id='OTHER'");c.commit()
   with self.assertRaises(ai.FeedbackError) as cm:material(c,1,1,1)
   self.assertEqual(cm.exception.code,'SAVED_ANSWER_PIN_MISMATCH')
  finally:c.close()
 def test_owned_snapshot_loader_rejects_withdrawn_release(self):
  app,native=self.install_fixture();self.c.execute("UPDATE integration_ph_content_releases SET local_status='WITHDRAWN'");self.c.commit()
  c=native.db()
  try:
   with self.assertRaises(ai.FeedbackError) as cm:app.extensions['scoremax_paid_ai_owned_material'](c,1,1,1)
   self.assertEqual(cm.exception.code,'RELEASE_NOT_CURRENTLY_AVAILABLE')
  finally:c.close()
 def test_provider_html_is_escaped_in_the_existing_result_ui(self):
  app,native=self.install_fixture();value=self.request()
  value['improvement']='<script>unsafe()</script>'
  with app.test_request_context('/'):
   from flask import render_template
   html=render_template('paid_ai_feedback.html',q=Q,feedback=value,attempt_id=1,question_id=1)
  self.assertNotIn('<script>unsafe()',html);self.assertIn('&lt;script&gt;',html)
 def test_provider_request_is_one_json_call_with_explicit_limits(self):
  from unittest.mock import patch
  class Transport:
   def open(inner,request,timeout):
    self.assertEqual(request.full_url,ai.ENDPOINT);body=json.loads(request.data)
    self.assertEqual(body['max_tokens'],768);self.assertEqual(body['thinking'],{'type':'disabled'})
    self.assertEqual(body['response_format'],{'type':'json_object'});self.assertNotIn('tools',body)
    self.assertEqual(timeout,12)
    class Reply:
     def __enter__(inner):return inner
     def __exit__(inner,*args):pass
     def read(inner,limit):return json.dumps({'choices':[{'finish_reason':'stop','message':{'content':json.dumps(VALID)}}],
       'usage':{'prompt_tokens':100,'completion_tokens':100}}).encode()
    return Reply()
  with patch('urllib.request.build_opener',return_value=Transport()) as opener:
   reply=ai.deepseek(ai.packet_from_native(Q,'x')[1],'synthetic-never-sent')
   self.assertEqual(reply.value,VALID);self.assertEqual(reply.usage,{'prompt_tokens':100,'completion_tokens':100})
   self.assertEqual(opener.call_count,1)


 def test_independent_reference_approval_is_required_by_benchmark_evaluator(self):
  path=ROOT/'scripts/evaluate_paid_ai_benchmark_20261026.py'
  spec=importlib.util.spec_from_file_location('reference_evaluator',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
  with self.assertRaisesRegex(ValueError,'INDEPENDENT_REFERENCE_MARK_APPROVAL_PENDING'):
   module.evaluate({'independent_reference_approval':{'status':'PENDING'},'cases':[]},[])
 def test_nonfinite_and_duplicate_provider_json_fields_are_rejected(self):
  for raw in ['{"total_marks":NaN}','{"total_marks":1,"total_marks":2}']:
   with self.assertRaises(ai.FeedbackError):ai.strict_json(raw)

if __name__=='__main__':unittest.main(verbosity=2)


