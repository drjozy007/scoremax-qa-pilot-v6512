"""Reuse the 67 programme/mastery regressions and add native DOM authority, switching and redirect regressions.

No product bootstrap or remote service is added; all fixtures are isolated and synthetic.
"""
from __future__ import annotations
import argparse,hashlib,json,unittest
from pathlib import Path
from qualify_programme_mastery_repair import ProgrammeMasteryRepair,ROOT

class ProgrammeMasteryNavigationRepair(ProgrammeMasteryRepair):
    def test_cosmetic_overlay_preserves_native_programme_and_subject_controls(self):
        response=self.client.get('/student/learn-vnext',base_url='https://localhost')
        self.assertEqual(response.status_code,200)
        html=response.get_data(as_text=True)
        self.assertNotIn("stack.querySelectorAll('.programme-context-strip').forEach(x=>x.remove())",html)
        self.assertNotIn('.student-context-stack .programme-context-strip{display:none!important}',html)
        self.assertNotIn("strip.innerHTML='';subjects.forEach",html)
        self.assertNotIn("if(!strip.querySelector('a'))subjects.forEach",html)
        self.assertIn('Subject navigation is server-owned.',html)
        self.assertNotIn("stack.appendChild(strip)",html)
        self.assertNotIn("grid.appendChild(a)",html)
        from qualify_assessment_contract_repair import Tags
        tags=Tags(html).tags
        for code in ('fsc1','fsc2','mdcat'):
            self.assertTrue(any(tag=='input' and attr.get('name')=='programme_code' and attr.get('value')==code for tag,attr in tags))
        self.assertTrue(any(tag=='form' and attr.get('action')=='/student/programme' and attr.get('method')=='post' for tag,attr in tags))
        self.assertEqual(self.programme(),'FSc Part 1')

    def test_native_live_programme_post_and_all_subject_card_destinations(self):
        from qualify_assessment_contract_repair import Tags
        # Only synthetic feature availability is changed; still exercise native POST/CSRF.
        self.c.execute("UPDATE users SET subjects='Biology,Chemistry,Physics,Mathematics' WHERE id=?",(self.uid,))
        self.c.execute("UPDATE feature_availability SET state='LIVE' WHERE feature_code IN ('programme_fsc2','programme_mdcat')")
        self.c.commit()
        for code,programme in [('fsc1','FSc Part 1'),('fsc2','FSc Part 2'),('mdcat','MDCAT')]:
            response=self.client.post('/student/programme',data={'_csrf_token':'synthetic-csrf','programme_code':code,'return_to':'/student/learn-vnext'},base_url='https://localhost')
            self.assertEqual(response.status_code,302)
            self.assertEqual(response.location,'/student/learn-vnext')
            self.assertEqual(self.programme(),programme)
            page=self.client.get(response.location,base_url='https://localhost')
            self.assertEqual(page.status_code,200)
            cards=[attr for tag,attr in Tags(page.text).tags if tag=='a' and 'ux-learn-card' in attr.get('class','').split()]
            self.assertGreaterEqual(len(cards),3)
            for card in cards:
                with self.subTest(programme=programme,card=card.get('href')):
                    dest=self.client.get(card['href'],base_url='https://localhost',follow_redirects=True)
                    self.assertEqual(dest.status_code,200)
                    self.assertEqual(self.programme(),programme)

    def test_native_programme_redirect_reuses_same_origin_security_helper(self):
        from urllib.parse import urlsplit
        for target in ('https://example.invalid/x','//example.invalid/x','/\\example.invalid','javascript:alert(1)','/x\r\nLocation: https://example.invalid'):
            with self.subTest(target=repr(target)):
                response=self.client.post('/student/programme',data={'_csrf_token':'synthetic-csrf','programme_code':'fsc1','return_to':target},base_url='https://localhost')
                self.assertEqual(response.status_code,302)
                self.assertFalse(urlsplit(response.location).netloc)
                self.assertEqual(response.location,'/student')


    def subject_links(self, path='/student/learn-vnext'):
        from qualify_assessment_contract_repair import Tags
        response=self.client.get(path,base_url='https://localhost')
        self.assertEqual(response.status_code,200)
        return [(a['data-subject'],a) for tag,a in Tags(response.text).tags if tag=='a' and 'data-subject' in a]

    def test_mdcat_shortcuts_use_exam_subjects_not_home_profile(self):
        self.c.execute("UPDATE users SET subjects='Mathematics,Physics,Chemistry,Biology' WHERE id=?",(self.uid,));self.c.commit()
        self.switch('MDCAT')
        links=self.subject_links()
        self.assertEqual([name for name,_ in links],['Biology','Chemistry','Physics','English','Logical Reasoning'])
        self.assertTrue(all('/catalogue/mdcat/' in a['href'] for _,a in links))
        self.assertEqual(self.programme(),'MDCAT')

    def test_fsc_shortcuts_follow_existing_declared_subjects_and_year(self):
        self.c.execute("UPDATE users SET subjects='Mathematics,Physics,English' WHERE id=?",(self.uid,));self.c.commit()
        for programme in ('FSc Part 1','FSc Part 2'):
            self.switch(programme)
            links=self.subject_links()
            self.assertEqual({name for name,_ in links},{'Physics','Mathematics'})
            self.assertEqual(self.programme(),programme)

    def test_all_subject_shortcut_destinations_keep_context(self):
        self.c.execute("UPDATE users SET subjects='Mathematics,Physics,Chemistry,Biology' WHERE id=?",(self.uid,))
        self.c.execute("UPDATE feature_availability SET state='LIVE' WHERE feature_code IN ('programme_fsc2','programme_mdcat')");self.c.commit()
        for programme in ('FSc Part 1','FSc Part 2','MDCAT'):
            self.switch(programme)
            for name,attr in self.subject_links():
                with self.subTest(programme=programme,subject=name):
                    response=self.client.get(attr['href'],base_url='https://localhost',follow_redirects=True)
                    self.assertEqual(response.status_code,200)
                    self.assertEqual(self.programme(),programme)

    def test_mdcat_subject_shortcut_active_state_is_exact(self):
        self.switch('MDCAT')
        self.c.execute("UPDATE feature_availability SET state='LIVE' WHERE feature_code='programme_mdcat'");self.c.commit()
        for subject in ('Biology','Chemistry','Physics','English','Logical Reasoning'):
            links=self.subject_links('/student/catalogue/mdcat/'+subject)
            self.assertEqual([name for name,a in links if 'active' in a.get('class','').split()],[subject])

    def test_existing_locked_subject_shortcut_keeps_access_redirect(self):
        from unittest.mock import patch
        from qualify_programme_mastery_repair import sm
        self.switch('MDCAT')
        locked=[{'subject':'Physics','access_state':'LOCKED','availability':'AVAILABLE','answered':0,'accuracy':0}]
        with patch.object(sm,'_subject_map',return_value=locked):
            links=dict(self.subject_links())
        self.assertIn('/account/access?',links['Physics']['href'])
        self.assertIn('locked_subject=Physics',links['Physics']['href'])

    def test_coach_and_install_offer_are_excluded_from_question_review_template(self):
        from qualify_programme_mastery_repair import sm
        for endpoint in ('take_test_v4','assessment_review_v4','ux_content_review_staged','ux_content_review_staged_question','ux_content_review_question','written_question_page'):
            with self.subTest(endpoint=endpoint),sm.app.test_request_context('/'):
                sm.request.url_rule=type('Rule',(),{'endpoint':endpoint})()
                sm.session.update(role='student')
                html=sm.render_template('base.html',show_scoremax_coach_global=endpoint not in {'take_test_v4','assessment_review_v4'},scoremax_coach_global={'title':'Synthetic','message':'Synthetic'})
                self.assertNotIn('id="scoremaxInstallNudge"',html)
                self.assertNotIn('id="coachDock"',html)

    def test_non_overlay_install_assets_and_native_later_control(self):
        html=self.client.get('/student/learn-vnext',base_url='https://localhost').text
        self.assertIn('id="scoremaxInstallLater"',html)
        css=(ROOT/'static/scoremax_install.css').read_text()
        self.assertIn('#scoremaxInstallNudge{position:static',css)
        self.assertNotIn('#scoremaxInstallNudge{position:fixed',css)
        js=(ROOT/'static/scoremax_install.js').read_text()
        self.assertIn("later?.addEventListener('click'",js)
        self.assertIn("sessionStorage.setItem(LATER_KEY,'1')",js)
        self.assertIn('const closeHelp=',js)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--report',default='programme_mastery_navigation_results.json');args=parser.parse_args()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ProgrammeMasteryNavigationRepair))
    report={'suite':'PROGRAMME_MASTERY_REPAIR_V3_BROWSER_CONTRACT','tests_run':result.testsRun,
      'failures':len(result.failures),'errors':len(result.errors),'passed':result.wasSuccessful(),
      'failure_names':[str(t) for t,_ in result.failures+result.errors],
      'source_hashes':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
        ['app.py','ux_student_batch.py','ux_catalogue_browser.py','ux_mastery_rigor_admin.py','ux_staging_routes.py']},
      'production_modified':False,'deployment_triggered':False,'full_mastery_model_frozen':False,
      'actual_curriculum_delivery_qualified':False,
      'scope':'Existing programme/mastery/navigation tests plus programme-scoped subject shortcuts, locks and non-obstructive controls. No real curriculum or bulk-import clearance.'}
    Path(args.report).write_text(json.dumps(report,indent=2)+'\n')
    print('PROGRAMME_MASTERY_REPAIR_RESULT='+json.dumps(report,sort_keys=True))
    raise SystemExit(0 if result.wasSuccessful() else 1)
