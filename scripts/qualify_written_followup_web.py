"""Real Flask and Chromium checks for the retained no-paid-API follow-up.
Synthetic data only; reuse native routes, sessions, DB and rendering, not doubles.
"""
from __future__ import annotations
import argparse,copy,hashlib,json,os,threading,unittest
from pathlib import Path
from urllib.parse import urlsplit
import qualify_written_entrypoints as fixture
from qualify_assessment_contract_repair import SPECS
sm=fixture.sm
UNKNOWN='I think the collisions explain why the tiny particle moves about.'
FULL=fixture.ANSWER

class FollowupWeb(fixture.WrittenEntryPoints):
    def setUp(self):
        super().setUp()
        payload=fixture.rubric()
        payload['scaffold_activities']=[dict(copy.deepcopy(q),id='SYN/'+name,title='Synthetic '+name) for name,(q,_) in SPECS.items()]
        self.qid,self.pid=self.written(payload)
        response=self.client.post(f'/written-practice/question/{self.qid}/submit',data={'_csrf_token':'synthetic-csrf','answer_text':UNKNOWN},base_url='https://localhost')
        self.assertEqual(response.status_code,302)
        self.aid=self.c.execute('SELECT id FROM written_attempts ORDER BY id DESC LIMIT 1').fetchone()[0]
        self.vid=self.c.execute('SELECT id FROM written_answer_versions WHERE attempt_id=? ORDER BY id LIMIT 1',(self.aid,)).fetchone()[0]
        self.path=f'/written-practice/attempt/{self.aid}'
        self.original=self.snapshot()
    def snapshot(self):
        result={}
        for key,sql,args in (
            ('attempt','SELECT * FROM written_attempts WHERE id=?',(self.aid,)),
            ('answer','SELECT * FROM written_answer_versions WHERE id=?',(self.vid,)),
            ('question','SELECT * FROM written_questions WHERE id=?',(self.qid,)),
            ('package','SELECT * FROM written_assessment_packages WHERE id=?',(self.pid,)),
            ('marking',"SELECT * FROM written_processing_jobs WHERE attempt_id=? AND job_type='MARKING'",(self.aid,))):
            result[key]=[dict(r) for r in self.c.execute(sql,args)]
        return result
    def unchanged(self):
        self.assertEqual(self.original,self.snapshot())
        for table in ('written_mastery_evidence','written_recovery_tasks','written_exemplar_candidates'):
            self.assertEqual(self.c.execute('SELECT COUNT(*) FROM '+table).fetchone()[0],0,table)
    def ctx(self):return sm.written_followup_context(self.c,self.aid,self.uid)
    def form(self,kind='clarify',answer=FULL,activity_id=''):
        ctx=self.ctx()
        return {'_csrf_token':'synthetic-csrf','followup_kind':kind,'followup_binding':ctx['binding'],
            'answer_version_id':str(ctx['answer_version_id']),'activity_id':activity_id,
            'answer_text' if kind=='clarify' else 'answer':answer}
    def post_followup(self,data=None,client=None):
        return (client or self.client).post(self.path+'/improve',data=self.form() if data is None else data,base_url='https://localhost')
    def outputs(self):
        return [json.loads(r[0]) for r in self.c.execute("SELECT output_json FROM written_processing_jobs WHERE attempt_id=? AND job_type='LOCAL_FOLLOWUP' ORDER BY id",(self.aid,))]
    def test_result_get_and_no_key_leak(self):
        response=self.client.get(self.path,base_url='https://localhost')
        self.assertEqual(response.status_code,200)
        self.assertIn('Check your understanding',response.text)
        self.assertIn('Your answer is saved, but not scored',response.text)
        for hidden in ('correct_option_ids','correct_mapping','required_mark_points','acceptable_paraphrases'):
            self.assertNotIn(hidden,response.text)
        self.unchanged()
    def test_full_clarification(self):
        self.assertEqual(self.post_followup().status_code,302)
        self.assertEqual(self.outputs()[0]['marks_awarded'],2)
        self.assertEqual(self.client.get(self.path,base_url='https://localhost').status_code,200)
        self.unchanged()
    def test_partial_clarification(self):
        self.assertEqual(self.post_followup(self.form(answer='Molecules collide with the particle.')).status_code,302)
        self.assertEqual(self.outputs()[0]['marks_awarded'],1);self.unchanged()
    def test_unknown_not_false_zero(self):
        self.assertEqual(self.post_followup(self.form(answer='No impacts occur because molecules are stationary.')).status_code,302)
        self.assertIsNone(self.outputs()[0]['marks_awarded'])
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM written_marking_runs').fetchone()[0],0);self.unchanged()
    def test_eight_approved_activity_formats(self):
        self.assertEqual(len(self.ctx()['activities']),8)
        for name,(_,answer) in SPECS.items():
            data=self.form('activity','', 'SYN/'+name);data.update(answer)
            self.assertEqual(self.post_followup(data).status_code,302,name)
            out=self.outputs()[-1];self.assertEqual(out['marks_awarded'],out['maximum_marks'],name)
        self.assertEqual(len(self.outputs()),8);self.unchanged()
    def test_idempotent_retry_and_conflict(self):
        data=self.form()
        self.assertEqual(self.post_followup(data).status_code,302)
        self.assertEqual(self.post_followup(data).status_code,302)
        self.assertEqual(len(self.outputs()),1)
        data['answer_text']='Molecules collide with the particle.'
        self.assertEqual(self.post_followup(data).status_code,409)
        self.assertEqual(len(self.outputs()),1);self.unchanged()
    def test_csrf_rejected(self):
        data=self.form();del data['_csrf_token']
        self.assertEqual(self.post_followup(data).status_code,400)
        self.assertEqual(self.outputs(),[]);self.unchanged()
    def test_other_learner_cannot_read_or_submit(self):
        other=self.client_for('syn-2')
        self.assertEqual(other.get(self.path,base_url='https://localhost').status_code,404)
        self.assertEqual(self.post_followup(client=other).status_code,404)
        self.assertEqual(self.outputs(),[]);self.unchanged()
    def test_stale_binding_rejected(self):
        data=self.form();data['followup_binding']='0'*64
        self.assertEqual(self.post_followup(data).status_code,409);self.unchanged()
    def test_withdrawn_question(self):
        data=self.form();self.c.execute('UPDATE written_questions SET active=0 WHERE id=?',(self.qid,));self.c.commit()
        self.assertEqual(self.post_followup(data).status_code,409);self.assertEqual(self.outputs(),[])
    def test_mock_cannot_use_practice_followup(self):
        data=self.form();self.c.execute("UPDATE written_attempts SET attempt_mode='mock' WHERE id=?",(self.aid,));self.c.commit()
        self.assertEqual(self.post_followup(data).status_code,302);self.assertEqual(self.outputs(),[])
    def test_feature_disabled(self):
        data=self.form();self.c.execute("UPDATE written_feature_controls SET state='HIDDEN' WHERE feature_code='written_response_engine'");self.c.commit()
        self.assertEqual(self.post_followup(data).status_code,403);self.assertEqual(self.outputs(),[])

def browser_checks(outdir):
    from werkzeug.serving import make_server
    from playwright.sync_api import sync_playwright
    test=FollowupWeb('test_full_clarification');test.setUp()
    app=sm.app;server=make_server('127.0.0.1',0,app,threaded=True,ssl_context='adhoc')
    base='https://localhost:'+str(server.server_port)
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    cookie=app.session_interface.get_signing_serializer(app).dumps({'user_id':test.uid,'role':'student','full_name':'Synthetic Browser Learner','session_version':0,'_csrf_token':'synthetic-csrf'})
    report={'passed':False,'cases':[],'javascript_errors':[],'external_requests_aborted':0,'live_records_used':False,'login_tested':False}
    out=Path(outdir);out.mkdir(parents=True,exist_ok=True)
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('CHROMIUM_EXECUTABLE') or None,args=['--no-sandbox','--disable-dev-shm-usage'])
            report['browser_version']=browser.version
            context=browser.new_context(ignore_https_errors=True,viewport={'width':390,'height':844})
            context.add_cookies([{'name':app.config['SESSION_COOKIE_NAME'],'value':cookie,'url':base,'secure':True,'httpOnly':True,'sameSite':'Lax'}])
            def guard(route):
                if urlsplit(route.request.url).hostname not in ('localhost','127.0.0.1'):
                    report['external_requests_aborted']+=1;route.abort()
                else:route.continue_()
            context.route('**/*',guard)
            page=context.new_page();page.on('pageerror',lambda e:report['javascript_errors'].append(str(e)))
            response=page.goto(base+test.path);assert response.status==200
            assert page.get_by_role('heading',name='Check your understanding',exact=True).is_visible()
            page.screenshot(path=str(out/'before_390.png'),full_page=True)
            for name,(_,answer) in SPECS.items():
                page.get_by_text('Synthetic '+name,exact=True).click()
                form=page.locator('form').filter(has=page.locator('input[name="activity_id"][value="SYN/'+name+'"]'))
                for key,value in answer.items():
                    field=form.locator('[name="'+key+'"]')
                    if key.startswith(('match::','order::')):field.select_option(value)
                    elif name in ('MCQ','TF','MR'):
                        for choice in value if isinstance(value,list) else [value]:form.locator('[name="answer"][value="'+choice+'"]').check()
                    else:field.fill(value)
                form.get_by_role('button',name='Check answer',exact=True).click();page.wait_for_load_state('domcontentloaded')
                result=test.outputs()[-1]
                assert result['marks_awarded']==result['maximum_marks'],(name,result)
                assert not result['independent_mastery_eligible'];test.unchanged()
                report['cases'].append({'format':name,'native_browser_submission':True,'passed':True})
            form=page.locator('form').filter(has=page.locator('input[name="followup_kind"][value="clarify"]'))
            form.locator('textarea[name="answer_text"]').fill(FULL)
            form.get_by_role('button',name='Check clarification',exact=True).click();page.wait_for_load_state('domcontentloaded')
            assert test.outputs()[-1]['marks_awarded']==2;test.unchanged()
            report['cases'].append({'format':'CLARIFICATION','passed':True})
            assert not report['javascript_errors'],report['javascript_errors']
            page.screenshot(path=str(out/'after_390.png'),full_page=True)
            page.set_viewport_size({'width':1365,'height':900});page.reload();assert page.locator('body').is_visible()
            page.screenshot(path=str(out/'after_1365.png'),full_page=True)
            report['passed']=len(report['cases'])==9;browser.close()
    except Exception as exc:
        report['error']=type(exc).__name__+': '+str(exc)
    finally:
        server.shutdown();worker.join(timeout=3);test.tearDown()
    return report

def main():
    p=argparse.ArgumentParser();p.add_argument('--report',required=True);p.add_argument('--browser',action='store_true');p.add_argument('--screenshots',default='/tmp/followup_screenshots');args=p.parse_args()
    names=sorted(n for n in FollowupWeb.__dict__ if n.startswith('test_'))
    result=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(FollowupWeb(n) for n in names))
    report={'suite':'NO_PAID_API_FOLLOWUP_REAL_FLASK_CHROMIUM_V1','http_tests':result.testsRun,'http_passed':result.wasSuccessful(),
        'failures':[str(t) for t,_ in result.failures+result.errors],'browser':None,'paid_ai_calls':0,'live_records_used':False,'actual18_qualified':False,
        'runtime_hashes':{n:hashlib.sha256((fixture.ROOT/n).read_bytes()).hexdigest() for n in ('app.py','written_response_engine.py','templates/written_result.html','templates/_learner_question_surface.html')}}
    if args.browser and report['http_passed']:report['browser']=browser_checks(args.screenshots)
    report['passed']=report['http_passed'] and (not args.browser or bool(report['browser'] and report['browser']['passed']))
    Path(args.report).write_text(json.dumps(report,indent=2)+'\n');print('WRITTEN_FOLLOWUP_WEB_RESULT='+json.dumps(report,sort_keys=True))
    return 0 if report['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
