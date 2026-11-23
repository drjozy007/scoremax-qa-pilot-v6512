"""Isolated Chromium mobile/3G acceptance on exact code and synthetic data only."""
from pathlib import Path
import argparse,sqlite3
import os,sys,json,importlib.util,shutil,threading,time,hashlib,urllib.parse
ROOT=Path(__file__).resolve().parents[2]
p=argparse.ArgumentParser();p.add_argument('runtime',type=Path);p.add_argument('seed',type=Path);p.add_argument('state',type=Path);p.add_argument('output',type=Path);a=p.parse_args();runtime=a.runtime.resolve();seed=a.seed.resolve();state=a.state.resolve();output=a.output.resolve()
assert os.environ.get('RENDER')!='true','OFFLINE_SOFTWARE_BROWSER_FIXTURE_ONLY'
assert all(x.is_relative_to(ROOT) for x in (runtime,seed,state,output)) and not state.exists()
def code_tree():return hashlib.sha256(json.dumps({p.relative_to(runtime).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in runtime.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'},sort_keys=True,separators=(',',':')).encode()).hexdigest()
assert code_tree()=='c32c7227b99fe38ee33ba612cb1a8b2f6154e0c0f6358fe67efa730fc1bb9c78','EXACT_FROZEN_APPLICATION_CODE_REQUIRED'

with sqlite3.connect(seed.as_uri()+'?mode=ro',uri=True) as c:
 assert c.execute("SELECT COUNT(*) FROM questions WHERE source_type='ISOLATED_SYNTHETIC_TEST'").fetchone()[0]==100800
 assert c.execute("SELECT COUNT(*) FROM users WHERE system_user_id LIKE 'SYN-STUDENT-%'").fetchone()[0]>=1001
(state/'state').mkdir(parents=True);database=state/'state/native.db';shutil.copy2(seed,database);sys.path[:0]=[str(ROOT/'dependencies_v1'),str(runtime),str(ROOT/'tests/biology_receiver_20261027')]

spec=importlib.util.spec_from_file_location('original_http',ROOT/'tests/navigation_perf_20261114/benchmark_gunicorn_http.py');b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b);os.environ.update(b.make_environment(database));os.environ.update(POWER_HOUSE_TO_SCOREMAX_TOKEN='software-ph-token',POWER_HOUSE_TO_SCOREMAX_HMAC_SECRET='software-ph-hmac',SCOREMAX_PUBLIC_BASE_URL='https://localhost:18879')
import scoremax_production
sm=scoremax_production.scoremax
from native_delivery_fixture import NativeDeliveryFixture
f=object.__new__(NativeDeliveryFixture);f.native=sm;f.integration=sm.integration_v1;f.runtime_path=runtime
spec=importlib.util.spec_from_file_location('mixed_image_fixture',ROOT/'tests/navigation_current_20261123/qualify_mixed_native_source_image_http_v1.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);protected=m.original_rows(database)
e=m.source_image_content(f);f.send_content(e);f.activate(e);uid=f.learner('mobile-v8');from werkzeug.security import generate_password_hash
password='SoftwareFixture_mobile_v8_only!';c=sm.db();c.execute("UPDATE users SET email=?,password_hash=?,access_override_code='level_1_access' WHERE id=?",('mobile-v8@scoremax.invalid',generate_password_hash(password),uid));c.commit();row=dict(c.execute('SELECT * FROM questions WHERE ph_question_id=?',(e['payload']['questions'][0]['question_id'],)).fetchone());c.close()
from werkzeug.serving import make_server
server=make_server('127.0.0.1',18879,scoremax_production.application,threaded=True,ssl_context='adhoc');thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
from playwright.sync_api import sync_playwright
observations=[];errors=[];failures=[];base='https://localhost:18879'
def metrics(page,label):
 r=page.evaluate("""() => {const n=performance.getEntriesByType('navigation')[0];return {ttfb_ms:n.responseStart-n.requestStart,dom_content_loaded_ms:n.domContentLoadedEventEnd,load_ms:n.loadEventEnd,transfer_bytes:n.transferSize,encoded_body_bytes:n.encodedBodySize,decoded_body_bytes:n.decodedBodySize,viewport_width:innerWidth,document_width:document.documentElement.scrollWidth,fcp_ms:performance.getEntriesByName('first-contentful-paint')[0]?.startTime??null}}""");r.update(stage=label,url=page.url.replace(base,''));observations.append(r);print('MOBILE_STAGE',json.dumps(r),flush=True);return r
def select_native_question_scope(form):
 programme=sm.integration_v1.question_contracts.programme_for_release(e['payload']['release']['programme_id'],sm.integration_v1.canonical_json(e['payload']['questions'][0]['curriculum']))
 form.locator('select[name=programme]').select_option(value=programme)
 form.locator('select[name=subject]').select_option(value=row['subject'])
 type_choices=form.locator('select[name=question_type] option').evaluate_all('(nodes)=>nodes.map(e=>({value:e.value,label:e.textContent}))');type_matches=[];c=sm.db()
 try:
  for choice in type_choices:
   if not choice['value']:continue
   clause,parameters=sm.practice_type_scope(choice['value'])
   if c.execute('SELECT COUNT(*) FROM questions q WHERE q.id=? AND '+clause,[row['id']]+parameters).fetchone()[0]==1:type_matches.append(choice)
 finally:c.close()
 assert len(type_matches)==1,('ACTUAL_UI_TYPE_MUST_RESOLVE_UNAMBIGUOUSLY_THROUGH_NATIVE_AUTHORITY',type_choices,type_matches)
 form.locator('select[name=question_type]').select_option(value=type_matches[0]['value'])
 choices=form.locator('select[name=chapter] option').evaluate_all('(nodes)=>nodes.map(e=>({value:e.value,label:e.textContent}))');matches=[];c=sm.db()
 try:
  for choice in choices:
   clause,parameters=sm._programme_chapter_scope_sql(programme,choice['value'],'q')
   if c.execute('SELECT COUNT(*) FROM questions q WHERE q.id=? AND '+sm.live_question_clause('q')+' AND '+clause,[row['id']]+parameters).fetchone()[0]==1:matches.append(choice)
 finally:c.close()
 print('NATIVE_BROWSER_SCOPE_RESOLUTION',json.dumps({'programme':programme,'subject':row['subject'],'source_qtype':row['qtype'],'native_type_choice':type_matches[0],'UI_choices':choices,'native_matching_choices':matches}),flush=True)
 assert len(matches)==1,'ACTUAL_UI_SCOPE_MUST_RESOLVE_UNAMBIGUOUSLY_THROUGH_NATIVE_AUTHORITY'
 form.locator('select[name=chapter]').select_option(value=matches[0]['value'])
 return {'chapter':matches[0],'question_type':type_matches[0]}
try:
 with sync_playwright() as p:
  binary=shutil.which('google-chrome') or shutil.which('chromium');assert binary,'EXISTING_CI_CHROMIUM_REQUIRED';browser=p.chromium.launch(executable_path=binary,headless=True,args=['--disable-dev-shm-usage']);context=browser.new_context(viewport={'width':390,'height':844},device_scale_factor=2,is_mobile=True,has_touch=True,ignore_https_errors=True);page=context.new_page();page.set_default_timeout(30000);page.on('pageerror',lambda e:errors.append(str(e)));page.on('dialog',lambda d:d.accept());page.on('requestfailed',lambda r:failures.append({'url':r.url.replace(base,''),'failure':r.failure}));cdp=context.new_cdp_session(page);cdp.send('Network.enable');cdp.send('Network.emulateNetworkConditions',{'offline':False,'latency':400,'downloadThroughput':65536,'uploadThroughput':16384,'connectionType':'cellular3g'})
  page.goto(base+'/login',wait_until='networkidle',timeout=90000);metrics(page,'cold_login');page.get_by_label('Email or ScoreMax ID').fill('mobile-v8@scoremax.invalid');page.get_by_label('Password',exact=True).fill('wrong-fixture-password');page.locator('form button').click();page.wait_for_load_state('networkidle');assert 'Invalid login details.' in page.locator('body').inner_text();page.get_by_label('Email or ScoreMax ID').fill('mobile-v8@scoremax.invalid');page.get_by_label('Password',exact=True).fill(password);page.locator('form button').click();page.wait_for_load_state('networkidle');assert '/login' not in page.url;metrics(page,'native_login_dashboard');later=page.get_by_role('button',name='Not now',exact=True);
  if later.is_visible():later.click();page.wait_for_load_state('networkidle')
  for label,path in [('learn','/student/learn-vnext'),('subject','/student/subject/Biology'),('chapter','/student/chapter?'+urllib.parse.urlencode({'subject':row['subject'],'chapter':row['chapter']})),('catalogue','/student/catalogue/year11/Biology')]:
   response=page.goto(base+path,wait_until='networkidle',timeout=90000);assert response.status==200;(state/(label+'.png')).write_bytes(page.screenshot(full_page=True));v=metrics(page,label);assert v['document_width']<=v['viewport_width']+1,(label,'HORIZONTAL_OVERFLOW')
  setup='/test/setup?'+urllib.parse.urlencode({'scope':'chapter','subject':row['subject'],'chapter':row['chapter']});assert page.goto(base+setup,wait_until='networkidle',timeout=90000).status==200;metrics(page,'setup');form=page.locator('form.test-builder-form');print('NATIVE_SETUP_FORM',form.inner_text()[:1800],flush=True);page.get_by_role('tab',name='Build My Own Test').click();selected_scope=select_native_question_scope(form);form.get_by_role('button',name='Build and start').click();page.wait_for_load_state('networkidle',timeout=90000);assert '/test/session/' in page.url,('NATIVE_START_FAILED',page.url,page.locator('body').inner_text()[:1200]);session_path=page.url.replace(base,'');sid=int(session_path.rsplit('/',1)[1]);metrics(page,'source_image_question');image=page.locator('img[src^="data:image/png;base64,"]');assert image.count()==1 and image.evaluate('(e)=>e.complete && e.naturalWidth===700 && e.naturalHeight===240');(state/'question.png').write_bytes(page.screenshot(full_page=True));page.locator('textarea[name=answer]').fill(str(e['payload']['questions'][0]['content']['marking']['key']));page.get_by_role('button',name='Review & Submit',exact=True).click();page.wait_for_load_state('networkidle',timeout=90000);metrics(page,'saved_review');print('NATIVE_REVIEW_BUTTONS',page.get_by_role('button').all_text_contents(),flush=True);page.get_by_role('button',name='Submit assessment',exact=True).click();page.wait_for_load_state('networkidle',timeout=90000);assert '/result/' in page.url;result_path=page.url.replace(base,'');assert 'Unscored' in page.locator('body').inner_text();assert page.locator('img[src^="data:image/png;base64,"]').evaluate('(e)=>e.complete && e.naturalWidth===700');metrics(page,'unscored_result');(state/'result.png').write_bytes(page.screenshot(full_page=True));f.send_stop(f.withdrawal('mobile-v8-stop',e['payload']['questions'][0],target=f.exact_target(e)));page.goto(base+result_path,wait_until='networkidle',timeout=90000);assert page.locator('img[src^="data:image/png;base64,"]').evaluate('(e)=>e.complete && e.naturalWidth===700');metrics(page,'historical_image_after_exact_withdrawal');assert not errors,errors;browser.close()
 c=sm.db()
 try:
  attempts=c.execute('SELECT * FROM attempts WHERE assessment_session_id=?',(sid,)).fetchall();assert len(attempts)==1 and attempts[0]['score'] is None and attempts[0]['total_marks_awarded'] is None;answer=c.execute('SELECT * FROM attempt_answers WHERE attempt_id=?',(attempts[0]['id'],)).fetchone();assert answer['marks_awarded'] is None and answer['mastery_evidence_eligible']==0;assert c.execute('SELECT COUNT(*) FROM mastery_records WHERE student_id=?',(uid,)).fetchone()[0]==0
 finally:c.close()
 m.preserved(database,protected);assert code_tree()=='c32c7227b99fe38ee33ba612cb1a8b2f6154e0c0f6358fe67efa730fc1bb9c78';report={'status':'PASSED_ISOLATED_CHROMIUM_MOBILE_3G_NATIVE_JOURNEY','runtime_tree_sha256':code_tree(),'native_UI_scope_choice':selected_scope,'viewport':[390,844],'download_KiB_s':64,'upload_KiB_s':16,'RTT_ms':400,'native_login_wrong_then_correct':True,'original_image_bytes':len(m.PNG),'native_answer_saved_and_unscored':True,'historical_original_image_preserved':True,'protected_tables':16,'page_errors':errors,'request_failures':failures,'observations':observations,'real_device_or_Render_network_acceptance':False,'production_actions':False};output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
finally:server.shutdown()
