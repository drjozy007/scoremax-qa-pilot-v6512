"""Eight real Chromium response journeys against isolated native HTTPS WSGI.

Authenticated synthetic sessions test delivery, not login. External requests are
aborted. Never connects to Render/PH or reads a live database.
"""
from __future__ import annotations
import argparse,json,os,threading
from pathlib import Path
from urllib.parse import urlsplit
from werkzeug.serving import make_server
from playwright.sync_api import sync_playwright
import qualify_assessment_contract_repair as fixture


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',default='assessment_browser_results.json');parser.add_argument('--screenshots',default='assessment_browser_screenshots');args=parser.parse_args()
    test=fixture.AssessmentRepair('test_native_eight_response_journeys');test.setUp()
    app=fixture.sm.app
    server=make_server('127.0.0.1',0,app,threaded=True,ssl_context='adhoc')
    base='https://localhost:'+str(server.server_port)
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    serializer=app.session_interface.get_signing_serializer(app)
    cookie=serializer.dumps({'user_id':test.uid,'role':'student','full_name':'Synthetic Browser Learner','session_version':0,'_csrf_token':'synthetic-csrf'})
    result={'suite':'REAL_CHROMIUM_ASSESSMENT_REPAIR','cases':[],'external_requests_aborted':0,'production_data_modified':False,'login_flow_tested':False,'passed':False}
    out=Path(args.screenshots);out.mkdir(parents=True,exist_ok=True)
    try:
        with sync_playwright() as pw:
            executable=os.environ.get('CHROMIUM_EXECUTABLE','')
            if not executable and Path('/usr/bin/chromium').is_file():executable='/usr/bin/chromium'
            browser=pw.chromium.launch(headless=True,executable_path=executable or None,args=['--no-sandbox','--disable-dev-shm-usage'])
            result['browser_version']=browser.version
            context=browser.new_context(ignore_https_errors=True,viewport={'width':390,'height':844})
            context.add_cookies([{'name':app.config['SESSION_COOKIE_NAME'],'value':cookie,'url':base,'secure':True,'httpOnly':True,'sameSite':'Lax'}])
            def route(req):
                if urlsplit(req.request.url).hostname not in {'localhost','127.0.0.1'}:
                    result['external_requests_aborted']+=1;req.abort()
                else:req.continue_()
            context.route('**/*',route)
            page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.on('dialog',lambda d:d.accept())
            def fill(name):
                _,form=fixture.SPECS[name]
                for key,values in form.items():
                    field=page.locator('[name="'+key+'"]')
                    if key.startswith(('match::','order::')):field.select_option(values)
                    elif name in {'MCQ','TF','MR'}:
                        for value in values if isinstance(values,list) else [values]:page.locator('[name="answer"][value="'+value+'"]').check()
                    else:field.fill(values)
            for name,(q,form) in fixture.SPECS.items():
                qid=test.insert(q);aid=test.start([qid]);url=base+f'/test/session/{aid}'
                response=page.goto(url);assert response.status==200,(name,response.status)
                fill(name)
                if name in {'MATCH','ORDER','WRITTEN'}:page.screenshot(path=str(out/(name+'_390.png')),full_page=True)
                page.get_by_role('button',name='Review & Submit',exact=True).click();page.wait_for_url('**/review')
                assert str(qid) in test.saved(aid),name
                page.goto(url)
                # Native form action: proves browser validation cannot trap a cleared answer.
                page.get_by_role('button',name='Clear answer',exact=True).click();page.wait_for_load_state('domcontentloaded')
                assert str(qid) not in test.saved(aid),name
                fill(name);page.get_by_role('button',name='Review & Submit',exact=True).click();page.wait_for_url('**/review')
                page.get_by_role('button',name='Submit assessment',exact=True).click();page.wait_for_url('**/result/*')
                a=test.attempt(aid);assert a['score']==100,(name,dict(a))
                assert not errors,(name,errors)
                result['cases'].append({'type':name,'mobile_viewport':'390x844','typed_saved_cleared_retyped_submitted':True,'score':a['score'],'passed':True})
            page.set_viewport_size({'width':1365,'height':900});page.screenshot(path=str(out/'result_1365.png'),full_page=True)
            result['javascript_errors']=errors;result['passed']=len(result['cases'])==8
            browser.close()
    finally:
        server.shutdown();worker.join(timeout=3);test.tearDown()
        Path(args.report).write_text(json.dumps(result,indent=2)+'\n')
        print('ASSESSMENT_BROWSER_RESULT='+json.dumps(result,sort_keys=True))
    return 0 if result['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
