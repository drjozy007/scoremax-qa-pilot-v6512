"""Real browser programme tabs/card paths and mastery slider draft/activate journey.

Isolated HTTPS WSGI, synthetic accounts and explicit synthetic feature availability.
No real login, live rollout flags, PH transport, or public-host operations are used.
"""
from __future__ import annotations
import argparse,json,os,threading
from pathlib import Path
from urllib.parse import urlsplit
from werkzeug.serving import make_server
from playwright.sync_api import sync_playwright
from qualify_programme_mastery_repair import ProgrammeMasteryRepair,sm,ux


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report',default='programme_mastery_browser.json');parser.add_argument('--screenshots',default='programme_mastery_browser_screenshots');args=parser.parse_args()
    test=ProgrammeMasteryRepair('test_fsc2_subject_cards_preserve_explicit_year');test.setUp()
    test.c.execute("UPDATE users SET subjects='Biology,Chemistry,Physics,Mathematics' WHERE id=?",(test.uid,))
    # Simulated launched programmes only; production flags remain untouched.
    test.c.execute("UPDATE feature_availability SET state='LIVE' WHERE feature_code IN ('programme_fsc2','programme_mdcat')");test.c.commit()
    test.answer_one('FSc Part 1')
    first=test.master_record('FSc Part 1');other=test.master_record('MDCAT')
    test.policy('programme','MDCAT',standard=50,status='ACTIVE')
    test.form_history('FSc Part 1')
    server=make_server('127.0.0.1',0,sm.app,threaded=True,ssl_context='adhoc');base='https://localhost:'+str(server.server_port)
    worker=threading.Thread(target=server.serve_forever,daemon=True);worker.start()
    serializer=sm.app.session_interface.get_signing_serializer(sm.app)
    result={'suite':'PROGRAMME_MASTERY_REAL_BROWSER_V3','cases':[],'javascript_errors':[],'external_requests_aborted':0,
      'passed':False,'production_data_modified':False,'login_flow_tested':False,'synthetic_feature_availability':True}
    out=Path(args.screenshots);out.mkdir(parents=True,exist_ok=True)
    try:
        with sync_playwright() as pw:
            executable=os.environ.get('CHROMIUM_EXECUTABLE','')
            if not executable and Path('/usr/bin/chromium').is_file():executable='/usr/bin/chromium'
            browser=pw.chromium.launch(headless=True,executable_path=executable or None,args=['--no-sandbox','--disable-dev-shm-usage'])
            result['browser_version']=browser.version
            def new_context(username,width):
                user=test.c.execute('SELECT * FROM users WHERE username=?',(username,)).fetchone()
                context=browser.new_context(ignore_https_errors=True,viewport={'width':width,'height':900})
                cookie=serializer.dumps({'user_id':user['id'],'role':user['role'],'full_name':user['full_name'],'session_version':user['session_version'] or 0,'_csrf_token':'synthetic-csrf'})
                context.add_cookies([{'name':sm.app.config['SESSION_COOKIE_NAME'],'value':cookie,'url':base,'secure':True,'httpOnly':True,'sameSite':'Lax'}])
                def intercept(route):
                    if urlsplit(route.request.url).hostname not in {'localhost','127.0.0.1'}:
                        result['external_requests_aborted']+=1;route.abort()
                    else:route.continue_()
                context.route('**/*',intercept)
                page=context.new_page();page.on('pageerror',lambda e:result['javascript_errors'].append(str(e)));page.on('dialog',lambda d:d.accept())
                return context,page
            for width in (390,1365):
                context,page=new_context('syn-1',width)
                for code,programme in [('fsc1','FSc Part 1'),('fsc2','FSc Part 2'),('mdcat','MDCAT')]:
                    response=page.goto(base+'/student/learn-vnext');assert response.status==200,response.status
                    form=page.locator('.programme-context-strip form').filter(has=page.locator(f'input[name="programme_code"][value="{code}"]'))
                    assert form.count()==1,(code,form.count())
                    with page.expect_navigation(wait_until='domcontentloaded'):
                        form.locator('button').click()
                    assert test.programme()==programme,(code,test.programme())
                    card=page.locator('a.ux-learn-card').filter(has=page.get_by_role('heading',name='Physics',exact=True))
                    assert card.count()==1,(code,card.count())
                    metrics=card.inner_text()
                    if code=='mdcat':assert '—' in metrics,metrics
                    href=card.get_attribute('href')
                    with page.expect_navigation(wait_until='domcontentloaded'):card.click()
                    assert test.programme()==programme,(code,test.programme())
                    names=page.locator('.ux-chapter-card h2,.ux-syllabus-card h2').all_text_contents()
                    assert names,(code,page.url)
                    if code=='mdcat':assert '/mdcat/' in urlsplit(page.url).path,page.url
                    page.screenshot(path=str(out/f'{code}_{width}.png'),full_page=True)
                    assert not result['javascript_errors'],result['javascript_errors']
                    result['cases'].append({'case':'programme_card','programme':programme,'viewport':width,'native_tab_post':True,
                      'card_href':href,'final_path':urlsplit(page.url).path,'chapter_or_unit_count':len(names),'chapter_titles':names,
                      'programme_preserved':True,'passed':True})
                context.close()
            context,page=new_context('admin',1365)
            response=page.goto(base+'/admin/mastery-rigor');assert response.status==200
            form=page.locator('form.mr-policy-form')
            form.locator('[name="name"]').fill('SYN-BROWSER-GLOBAL')
            form.locator('[name="policy_version"]').fill('SYN-BROWSER-V1')
            form.locator('[name="reason"]').fill('Synthetic browser qualification')
            # Exercise real keyboard-operable sliders, not a form POST shortcut.
            form.locator('[name="rigor_score"]').focus();form.locator('[name="rigor_score"]').press('Home')
            form.locator('[name="mastery_standard_score"]').focus();form.locator('[name="mastery_standard_score"]').press('End')
            assert form.locator('[name="rigor_score"]').input_value()=='0'
            assert form.locator('[name="mastery_standard_score"]').input_value()=='100'
            with page.expect_navigation(wait_until='domcontentloaded'):
                form.get_by_role('button',name='Save Draft & Preview Impact',exact=True).click()
            policy=test.c.execute("SELECT * FROM assessment_assembly_policies WHERE name='SYN-BROWSER-GLOBAL'").fetchone()
            assert policy and policy['status']=='DRAFT' and policy['rigor_score']==0 and policy['mastery_standard_score']==100
            assert test.status(first)=='Verified' and test.status(other)=='Verified'
            assert json.loads(policy['preview_json'])['historical_simulation']['observed_forms']==1
            row=page.locator('.mr-policy-table tbody tr').filter(has_text='SYN-BROWSER-GLOBAL')
            row.locator('[name="reason"]').fill('Synthetic explicit activation')
            with page.expect_navigation(wait_until='domcontentloaded'):row.get_by_role('button',name='Activate',exact=True).click()
            assert test.status(first)=='Verification Due'
            assert test.status(other)=='Verified' # The specific MDCAT policy still takes precedence.
            page.screenshot(path=str(out/'mastery_rigor_1365.png'),full_page=True)
            result['cases'].append({'case':'mastery_sliders_draft_activate','rigor':0,'mastery_standard':100,
              'draft_did_not_change_mastery':True,'explicit_activation':True,'specific_mdcat_policy_preserved':True,'passed':True})
            result['passed']=len(result['cases'])==7 and not result['javascript_errors']
            browser.close()
    finally:
        server.shutdown();worker.join(timeout=3);test.tearDown()
        Path(args.report).write_text(json.dumps(result,indent=2)+'\n');print('PROGRAMME_MASTERY_BROWSER_RESULT='+json.dumps(result,sort_keys=True))
    return 0 if result['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
