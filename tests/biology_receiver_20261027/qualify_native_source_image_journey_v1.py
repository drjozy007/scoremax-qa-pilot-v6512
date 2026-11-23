"""Native learner browse/start/save/submit flow while API marking remains off."""
import argparse,json,sys,base64,hashlib
from copy import deepcopy
from pathlib import Path
from urllib.parse import urlsplit
from html.parser import HTMLParser
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tests/biology_receiver_20261027'));sys.path.insert(0,str(ROOT/'tests/biology_receiver_20261027'))
from native_delivery_fixture import NativeDeliveryFixture
PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=')
URI='data:image/png;base64,'+base64.b64encode(PNG).decode()

class Hidden(HTMLParser):
 def __init__(self,text):super().__init__();self.values={};self.feed(text)
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='input' and a.get('type')=='hidden' and a.get('name'):self.values[a['name']]=a.get('value','')

def run(runtime,state):
 f=NativeDeliveryFixture(runtime,state);n=f.native
 from pending_saq_software_fixture_20261122 import content
 import ux_content_reviewer as reviewer
 reviewer.install_content_reviewer(n.app)
 import ux_catalogue_browser as catalogue
 catalogue.install_catalogue_browser(n.app)
 observed=[]
 try:
  for maximum in (1,2,3,4):
   e=content(f,'pending-image-'+str(maximum),maximum);q=e['payload']['questions'][0]
   stimulus={'stimulus_id':'opaque::image/'+str(maximum),'stimulus_version_id':'opaque::image-version/'+str(maximum),
      'stimulus_type':'IMAGE_REFERENCE','content':{'uri':URI,'file_sha256':hashlib.sha256(PNG).hexdigest(),'mime_type':'image/png'},
      'provenance':deepcopy(q['provenance']['primary_source'])}
   stimulus['stimulus_checksum_sha256']=f.integration._object_checksum(stimulus,'stimulus_checksum_sha256')
   q['content']['stimulus_ref']=stimulus['stimulus_id'];q['question_checksum_sha256']=f.integration._object_checksum(q,'question_checksum_sha256')
   e['payload']['stimuli']=[stimulus];e['payload']['release']['stimulus_count']=1;f.seal(e);f.send_content(e);f.send_content(e);f.activate(e)
   uid=f.learner('pending-browser-'+str(maximum));c=n.db()
   try:
    row=dict(c.execute('SELECT * FROM questions WHERE ph_question_id=?',(q['question_id'],)).fetchone());programme=n.integration_v1.question_contracts.programme_for_release(e['payload']['release']['programme_id'],n.integration_v1.canonical_json(q['curriculum']))
   finally:c.close()
   with n.app.test_client() as client:
    with client.session_transaction() as browser:browser.update(user_id=uid,role='student',session_version=0,_csrf_token='software-browser-csrf')
    chapter=client.get('/student/chapter',query_string={'subject':row['subject'],'chapter':row['chapter']});assert chapter.status_code==200
    text=chapter.get_data(as_text=True);assert 'active questions' in text and 'active scored questions' not in text
    setup=client.get('/test/setup',query_string={'scope':'chapter','subject':row['subject'],'chapter':row['chapter']});assert setup.status_code==200
    form={'subject':row['subject'],'chapter':row['chapter'],'programme':programme,'scope':'chapter','count':'1','mode':'practice','question_type':'Constructed Response','_csrf_token':'software-browser-csrf'}
    denied=client.post('/test/start',data=form)
    assert denied.status_code==302 and '/test/session/' not in denied.headers.get('Location',''),'FOUNDATION_BYPASSED_EXISTING_EXAM_READY_ACCESS'
    c=n.db()
    try:
     assert c.execute('SELECT COUNT(*) FROM assessment_sessions WHERE student_id=?',(uid,)).fetchone()[0]==0
     c.execute("UPDATE users SET access_override_code='level_1_access' WHERE id=?",(uid,));c.commit()
     assert n.get_access_profile(c,uid)['mastery_ceiling']=='Exam Ready'
    finally:c.close()
    started=client.post('/test/start',data=form)
    assert started.status_code==302 and '/test/session/' in started.headers.get('Location',''),(started.status_code,started.headers.get('Location'))
    session_path=urlsplit(started.headers['Location']).path;sid=session_path.rsplit('/',1)[1]
    question=client.get(session_path);assert question.status_code==200
    assert ('src="'+URI+'"') in question.get_data(as_text=True) and '<img ' in question.get_data(as_text=True)
    fields=Hidden(question.get_data(as_text=True)).values;fields.update(_csrf_token='software-browser-csrf',response_present='1',action='review',answer=str(q['content']['marking']['key']))
    saved=client.post(session_path,data=fields);assert saved.status_code==302
    for _ in range(2):
     submitted=client.post(session_path+'/submit',data={'_csrf_token':'software-browser-csrf'});assert submitted.status_code==302
    c=n.db()
    try:
     attempts=c.execute('SELECT * FROM attempts WHERE assessment_session_id=?',(sid,)).fetchall();assert len(attempts)==1;a=attempts[0]
     assert a['score'] is None and a['total_marks_awarded'] is None and a['maximum_marks']==maximum
     answer=c.execute('SELECT * FROM attempt_answers WHERE attempt_id=?',(a['id'],)).fetchone();assert answer['marks_awarded'] is None and answer['mastery_evidence_eligible']==0
     assert row['marks']==maximum and row['ph_independent_mastery_weight']==1
     assert not n.learner_answer_evidence(c,uid,programme)
     pin=c.execute('SELECT ph_question_pins_json FROM assessment_sessions WHERE id=?',(sid,)).fetchone()[0];assert URI not in pin and 'ph_learner_image_ref' in pin
     assert c.execute('SELECT COUNT(*) FROM integration_ph_stimulus_version_store WHERE stimulus_id=?',(stimulus['stimulus_id'],)).fetchone()[0]==1
    finally:c.close()
    result=client.get('/result/'+str(a['id']));assert result.status_code==200 and '<div class="score">Unscored</div>' in result.get_data(as_text=True)
    assert ('src="'+URI+'"') in result.get_data(as_text=True), 'PINNED_IMAGE_MISSING_FROM_SAVED_ATTEMPT_REVIEW'
   f.send_stop(f.withdrawal('pending-browser-stop-'+str(maximum),q,target=f.exact_target(e)))
   with n.app.test_client() as client:
    with client.session_transaction() as browser:browser.update(user_id=uid,role='student',session_version=0,_csrf_token='software-browser-csrf')
    historical=client.get('/result/'+str(a['id']));assert historical.status_code==200 and ('src="'+URI+'"') in historical.get_data(as_text=True)
   observed.append({'exact_signed_image_on_question_and_result':True,'image_preserved_after_withdrawal':True,'image_bytes_not_copied_to_session_pin':True,'source_marks':maximum,'source_weight':1,'actual_chapter_browse':True,'actual_test_setup_and_start':True,'foundation_access_remains_fenced':True,'native_exam_ready_access_used':True,'actual_saved_answer_and_repeat_submit':True,'saved_unscored_and_no_formal_mastery':True,'header_has_no_false_scored_claim':True,'signed_withdrawal':True})
  c=n.db()
  try:assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok';assert not c.execute('PRAGMA foreign_key_check').fetchall()
  finally:c.close()
 finally:
  m=sys.modules.get('navigation_request_connections_v1')
  if m is not None and hasattr(m,'clear_idle'):m.clear_idle()
 return {'status':'PASSED_NATIVE_SIGNED_IMAGE_LEARNER_HTTP_JOURNEY','browser_visual_acceptance':False,'observations':observed,'academic_authority':'SOFTWARE_FIXTURES_ONLY','official_ai_scoring_enabled':False,'production_actions':False}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('runtime',type=Path);p.add_argument('state',type=Path);p.add_argument('output',type=Path);a=p.parse_args();r=run(a.runtime.resolve(),a.state.resolve());a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
