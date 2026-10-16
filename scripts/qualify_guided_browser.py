"""Actual assembled routes in a disposable browser; synthetic account/content only."""
import argparse
import json
import os
from pathlib import Path
import threading
from urllib.parse import urlsplit
from werkzeug.serving import make_server
from playwright.sync_api import sync_playwright
from qualify_assessment_contract_repair import AssessmentRepair,sm
from qualify_guided_self_assessment import fixture


def main():
    p=argparse.ArgumentParser();p.add_argument('--report',default='guided_browser.json');a=p.parse_args()
    test=AssessmentRepair('test_schema_integrity_after_all_operations');test.setUp()
    server=make_server('127.0.0.1',0,sm.app,threaded=True,ssl_context='adhoc')
    base='https://localhost:'+str(server.server_port)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    serializer=sm.app.session_interface.get_signing_serializer(sm.app)
    report={'passed':False,'synthetic_only':True,'production_mutations':False,'surfaces':[]}
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,executable_path=os.environ.get('CHROMIUM_EXECUTABLE') or None,args=['--no-sandbox'])
            report['browser']=browser.version
            qid=test.insert(fixture())
            test.c.execute("UPDATE questions SET level='Foundation' WHERE id=?",(qid,));test.c.commit()
            for width in (390,1365):
                context=browser.new_context(ignore_https_errors=True,viewport={'width':width,'height':900})
                user=test.c.execute('SELECT * FROM users WHERE id=?',(test.uid,)).fetchone()
                cookie=serializer.dumps({'user_id':test.uid,'role':'student','full_name':user['full_name'],'session_version':0,'_csrf_token':'synthetic-csrf'})
                context.add_cookies([{'name':sm.app.config['SESSION_COOKIE_NAME'],'value':cookie,'url':base,'secure':True,'httpOnly':True,'sameSite':'Lax'}])
                context.route('**/*',lambda route:route.continue_() if urlsplit(route.request.url).hostname in ('localhost','127.0.0.1') else route.abort())
                page=context.new_page();page.on('dialog',lambda dialog:dialog.accept())
                page.goto(base+'/test/setup')
                page.get_by_role('link',name='Guided written practice · no score',exact=True).click()
                assert page.get_by_label('Practice type',exact=True).input_value()=='GUIDED_SELF_ASSESSMENT'
                page.get_by_role('button',name='Build and start',exact=True).click()
                page.wait_for_url('**/test/session/*')
                aid=int(page.url.rsplit('/',1)[-1])
                assert fixture()['answer'] not in page.content()
                page.get_by_label('Your answer',exact=True).fill('My independently written description.')
                page.get_by_role('button',name='Review & Submit',exact=True).click()
                page.get_by_role('button',name='Submit assessment',exact=True).click()
                page.get_by_role('heading',name='Compare and improve',exact=True).wait_for()
                assert page.get_by_text(fixture()['answer'],exact=True).is_visible()
                assert page.locator('fieldset').count()==2
                page.locator('fieldset').nth(0).get_by_label('Demonstrated',exact=True).check()
                page.locator('fieldset').nth(1).get_by_label('Unsure',exact=True).check()
                page.get_by_role('button',name='Save self-review',exact=True).click()
                assert page.locator('input[value="demonstrated"]').first.is_checked()
                assert page.locator('input[value="unsure"]').nth(1).is_checked()
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
                Path('guided_browser_screenshots').mkdir(exist_ok=True)
                page.screenshot(path=f'guided_browser_screenshots/review-{width}.png',full_page=True)
                page.get_by_role('button',name='Write an improved answer',exact=True).click()
                assert page.get_by_label('Your answer',exact=True).input_value()==''
                assert page.get_by_text('This is an improvement attempt after viewing the answer.',exact=True).is_visible()
                assert test.saved(aid)=={str(qid):'My independently written description.'}
                assert test.c.execute('SELECT COUNT(*) FROM attempts').fetchone()[0]==0
                report['surfaces'].append({'width':width,'guided_only_subject_entry':True,'write_save_reveal_self_review_retry':True,'labelled_controls':True,'no_horizontal_overflow':True,'scores_created':0})
                context.close()
            browser.close();report['passed']=True
    finally:
        server.shutdown();test.tearDown();Path(a.report).write_text(json.dumps(report,indent=2))


if __name__=='__main__':main()
