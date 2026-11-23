"""Disposable UK11 synthetic tests; no real student records or API calls."""
from __future__ import annotations
import copy
import json
import os
import sqlite3
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from ai_explanation_candidate import ExplanationHold
from uk11_result_explanation import FLAG, enabled, read_explanation, install
from ux_uk11_explain_overlay import apply, RESULT_MARKER

PIN = dict(question_id='Q11-SYN',question_version_id='V11-SYN',question_checksum_sha256='H-SYN',
           release_id='R-UK-SYN',release_version='1',release_checksum_sha256='CH-SYN',market_id='UK')
GOV = dict(academic_review_state='APPROVED',hold_status='CLEAR',release_readiness='READY',
           source_check_status='CLEAR',r2_status='NOT_REQUIRED',rights_status='OWNED')
ARCH = dict(evidence_role='INDEPENDENT',independent_mastery_eligible=True,independent_mastery_weight=1)
CONTENT = dict(stem='What is 12 divided into three equal parts?',
               marking=dict(key_type='NUMERIC',key='4',explanation='Three equal groups of 4 make 12. Divide 12 by 3 to get 4.'))

class FakeIntegration:
    @staticmethod
    def _governance_ready(q):
        g=q['governance'];a=q['architecture']
        required={'academic_review_state':'APPROVED','hold_status':'CLEAR','release_readiness':'READY'}
        if any(g.get(k)!=v for k,v in required.items()):return False,'GOVERNANCE_HOLD'
        if g.get('source_check_status') not in ('CLEAR','NOT_REQUIRED'):return False,'SOURCE_CHECK'
        if g.get('r2_status') not in ('CLEARED','NOT_REQUIRED','PASSED','COMPLETE'):return False,'R2'
        if g.get('rights_status') not in ('OWNED','COMMISSIONED_IP_ASSIGNED','LICENSED_COMMERCIAL','OPEN_COMMERCIAL','PUBLIC_DOMAIN'):return False,'RIGHTS'
        return True,''

class Native:
    integration_v1=FakeIntegration()

class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.db=Path(self.temp.name)/'synthetic.db'
        self.c=self.connect()
        self.c.executescript('''
          CREATE TABLE attempts(id INTEGER PRIMARY KEY,student_id INTEGER,assessment_session_id INTEGER);
          CREATE TABLE assessment_sessions(id INTEGER PRIMARY KEY,student_id INTEGER,status TEXT);
          CREATE TABLE questions(id INTEGER PRIMARY KEY,active INTEGER,status TEXT,question TEXT,answer TEXT,
            explanation TEXT,topic TEXT,qtype TEXT,stimulus_type TEXT,subject TEXT,capsule_id TEXT,ph_market_id TEXT,ph_is_auto_markable INTEGER);
          CREATE TABLE attempt_answers(attempt_id INTEGER,question_db_id INTEGER,selected_answer TEXT,
            is_correct INTEGER,marks_awarded REAL,marking_status TEXT,
            ph_question_id TEXT,ph_question_version_id TEXT,ph_question_checksum_sha256 TEXT,
            ph_release_id TEXT,ph_release_version TEXT,ph_release_checksum_sha256 TEXT);
          CREATE TABLE integration_ph_question_version_store(question_id TEXT,question_version_id TEXT,
            question_checksum_sha256 TEXT,curriculum_json TEXT,content_json TEXT,architecture_json TEXT,governance_json TEXT);
          CREATE TABLE integration_ph_release_question_membership(release_id TEXT,release_version TEXT,question_id TEXT,question_version_id TEXT);
          CREATE TABLE integration_ph_content_releases(release_id TEXT,release_version TEXT,package_checksum_sha256 TEXT,local_status TEXT);
          CREATE TABLE integration_ph_product_activation_authorizations(release_id TEXT,release_version TEXT,
            package_checksum_sha256 TEXT,activation_status TEXT);
          CREATE TABLE ph_bridge_staged_withdrawal_exclusions_v6611e(release_id TEXT,release_version TEXT,question_id TEXT,question_version_id TEXT);
          CREATE TABLE learning_capsules(capsule_id TEXT,subject TEXT,review_status TEXT,active INTEGER,
            simple_explanation TEXT,remember_this TEXT,worked_example TEXT,common_mistake TEXT,memory_tip TEXT);
          INSERT INTO attempts VALUES(1,1,1);
          INSERT INTO assessment_sessions VALUES(1,1,'submitted');
          INSERT INTO questions VALUES(1,1,'Approved','What is 12/3?','4','Explanation','Division','Numerical','','Maths','cap11','UK',1);
          INSERT INTO attempt_answers VALUES(1,1,'6',0,0,NULL,'Q11-SYN','V11-SYN','H-SYN','R-UK-SYN','1','CH-SYN');
          INSERT INTO integration_ph_release_question_membership VALUES('R-UK-SYN','1','Q11-SYN','V11-SYN');
          INSERT INTO integration_ph_content_releases VALUES('R-UK-SYN','1','CH-SYN','ACTIVE');
          INSERT INTO integration_ph_product_activation_authorizations VALUES('R-UK-SYN','1','CH-SYN','ACTIVATED');
          INSERT INTO learning_capsules VALUES('cap11','Maths','Approved',1,'Divide into equal groups.',
            'Equal groups mean division.','15 / 3 = 5','Do not multiply by the group count.','Check your groups.');
        ''')
        self.c.execute('INSERT INTO integration_ph_question_version_store VALUES(?,?,?,?,?,?,?)',(
            PIN['question_id'],PIN['question_version_id'],PIN['question_checksum_sha256'],json.dumps({'market_id':'UK'}),
            json.dumps(CONTENT),json.dumps(ARCH),json.dumps(GOV)))
        self.c.commit()
    def tearDown(self):self.c.close();self.temp.cleanup()
    def connect(self):
        c=sqlite3.connect(self.db);c.row_factory=sqlite3.Row;return c
    def owned(self,c,attempt_id,question_id,student_id):
        # Minimal proxy matching existing native written_ai_adapter.owned_material authority.
        row=c.execute('''SELECT aa.*,a.assessment_session_id FROM attempt_answers aa
          JOIN attempts a ON a.id=aa.attempt_id WHERE a.student_id=?
          AND aa.attempt_id=? AND aa.question_db_id=?''',(student_id,attempt_id,question_id)).fetchone()
        if not row:raise ExplanationHold('ASSESSMENT_NOT_FOUND')
        a=c.execute('SELECT status FROM assessment_sessions WHERE id=? AND student_id=?',
                   (row['assessment_session_id'],student_id)).fetchone()
        if not a or a['status']!='submitted':raise ExplanationHold('SUBMITTED_ASSESSMENT_REQUIRED')
        q=c.execute("SELECT * FROM questions WHERE id=? AND active=1 AND status='Approved'",(question_id,)).fetchone()
        if not q:raise ExplanationHold('QUESTION_NOT_CURRENTLY_AVAILABLE')
        exists=c.execute('''SELECT 1 FROM integration_ph_content_releases r
          WHERE r.release_id=? AND r.release_version=? AND r.package_checksum_sha256=?
          AND r.local_status='ACTIVE'
          AND EXISTS (SELECT 1 FROM integration_ph_product_activation_authorizations a
            WHERE a.release_id=r.release_id AND a.release_version=r.release_version
            AND a.package_checksum_sha256=r.package_checksum_sha256
            AND a.activation_status IN ('AUTHORIZED','ACTIVATED'))
          AND NOT EXISTS (SELECT 1 FROM ph_bridge_staged_withdrawal_exclusions_v6611e w
            WHERE w.release_id=r.release_id AND w.release_version=r.release_version
            AND w.question_id=? AND w.question_version_id=?)''',
            (PIN['release_id'],PIN['release_version'],PIN['release_checksum_sha256'],PIN['question_id'],PIN['question_version_id'])).fetchone()
        if not exists:raise ExplanationHold('RELEASE_NOT_CURRENTLY_AVAILABLE')
        return row,q,PIN
    def explanation(self,**kwargs):
        with patch.dict(os.environ,{FLAG:'1'}):
            return read_explanation(self.c,Native(),attempt_id=1,question_id=1,student_id=1,
                                    owned=self.owned,**kwargs)
    def hold(self,code):
        with self.assertRaises(ExplanationHold) as r:self.explanation()
        self.assertEqual(r.exception.code,code)
    def test_feature_flag_off_by_default(self):
        with patch.dict(os.environ,{FLAG:'0'}):
            self.assertFalse(enabled())
            with self.assertRaisesRegex(ExplanationHold,'UK_EXPLANATION_FEATURE_DISABLED'):
                read_explanation(self.c,Native(),attempt_id=1,question_id=1,student_id=1,owned=self.owned)
    def test_read_only_approved_wrong_answer_and_capsule(self):
        before=self.c.total_changes
        data=self.explanation()
        self.assertIn('Divide 12 by 3',data['simple_explanation'])
        self.assertEqual(data['learning_capsule']['simple_explanation'],'Divide into equal groups.')
        self.assertTrue(data['official_mark_unchanged'])
        self.assertTrue(data['mastery_unchanged'])
        self.assertNotIn('_source_pin',data)
        self.assertEqual(before,self.c.total_changes)
    def test_other_student_denied(self):
        with patch.dict(os.environ,{FLAG:'1'}):
            with self.assertRaisesRegex(ExplanationHold,'ASSESSMENT_NOT_FOUND'):
                read_explanation(self.c,Native(),attempt_id=1,question_id=1,student_id=2,owned=self.owned)
    def test_unsubmitted_denied(self):
        self.c.execute("UPDATE assessment_sessions SET status='in_progress'");self.hold('SUBMITTED_ASSESSMENT_REQUIRED')
    def test_correct_answer_denied(self):
        self.c.execute('UPDATE attempt_answers SET is_correct=1');self.hold('INCORRECT_ANSWER_REQUIRED')
    def test_blank_response_denied(self):
        self.c.execute("UPDATE attempt_answers SET selected_answer=''");self.hold('SUBMITTED_ANSWER_REQUIRED')
    def test_unscored_response_denied(self):
        self.c.execute("UPDATE attempt_answers SET marking_status='AUTO_UNSCORED'");self.hold('CONFIRMED_NATIVE_MARK_REQUIRED')
    def test_stale_pin_denied(self):
        self.c.execute("UPDATE attempt_answers SET ph_question_version_id='V-OTHER'");self.hold('SAVED_ANSWER_PIN_MISMATCH')
    def test_stored_question_checksum_mismatch_denied(self):
        self.c.execute("UPDATE integration_ph_question_version_store SET question_checksum_sha256='TAMPERED'")
        self.hold('CANONICAL_VERSION_PIN_MISMATCH')
    def test_non_uk_canonical_denied(self):
        self.c.execute("UPDATE integration_ph_question_version_store SET curriculum_json=?", (json.dumps({"market_id":"PK"}),))
        self.hold('UK_ONLY_CANONICAL_CONTENT_REQUIRED')
    def test_non_uk_display_denied(self):
        self.c.execute("UPDATE questions SET ph_market_id='PK'");self.hold('UK_ONLY_CANONICAL_CONTENT_REQUIRED')
    def test_wrong_market_pin_held(self):
        original=PIN.get('market_id')
        try:
            PIN['market_id']='PK'
            self.hold('UK_RELEASE_PIN_REQUIRED')
        finally:
            PIN['market_id']=original
    def test_unapproved_membership_denied(self):
        self.c.execute('DELETE FROM integration_ph_release_question_membership')
        self.hold('EXACT_ROUTE_MEMBERSHIP_REQUIRED')
    def test_unqualified_native_marking_denied(self):
        self.c.execute('UPDATE questions SET ph_is_auto_markable=0')
        self.hold('NATIVE_SCORING_MODE_UNQUALIFIED')
    def test_legacy_answer_cannot_override_approved_canonical_answer(self):
        self.c.execute("UPDATE questions SET answer='999'")
        out=self.explanation()
        self.assertIn('Divide 12 by 3',out['simple_explanation'])
        self.assertNotIn('999',json.dumps(out))
    def test_governance_hold_denied(self):
        self.c.execute('UPDATE integration_ph_question_version_store SET governance_json=?',
                       (json.dumps(dict(GOV,academic_review_state='PENDING')),));self.hold('ACADEMIC_GOVERNANCE_NOT_READY')
    def test_rights_hold_denied(self):
        self.c.execute('UPDATE integration_ph_question_version_store SET governance_json=?',
                       (json.dumps(dict(GOV,rights_status='UNRESOLVED')),));self.hold('ACADEMIC_GOVERNANCE_NOT_READY')
    def test_rubric_only_denied(self):
        self.c.execute('UPDATE integration_ph_question_version_store SET content_json=?',
                       (json.dumps(dict(CONTENT,marking={'key_type':'RUBRIC_ONLY','explanation':'No'})),))
        self.hold('UNQUALIFIED_RESPONSE_TYPE')
    def test_visual_and_stimulus_held(self):
        for extra in ({'stimulus_ref':'S1'}, {'inline_stimulus':{'text':'Passage'}},):
            with self.subTest(extra=extra):
                self.c.execute('UPDATE integration_ph_question_version_store SET content_json=?',(json.dumps(dict(CONTENT,**extra)),))
                self.hold('STIMULUS_EXPLANATION_NEEDS_QUALIFICATION')
    def test_withdrawal_and_inactive_release_denied(self):
        self.c.execute("UPDATE integration_ph_content_releases SET local_status='WITHDRAWN'")
        self.hold('RELEASE_NOT_CURRENTLY_AVAILABLE')
        self.c.execute("UPDATE integration_ph_content_releases SET local_status='ACTIVE'")
        self.c.execute("INSERT INTO ph_bridge_staged_withdrawal_exclusions_v6611e VALUES('R-UK-SYN','1','Q11-SYN','V11-SYN')")
        self.hold('RELEASE_NOT_CURRENTLY_AVAILABLE')
    def test_missing_native_governance_not_assumed(self):
        class Missing: pass
        with patch.dict(os.environ,{FLAG:'1'}):
            with self.assertRaisesRegex(ExplanationHold,'NATIVE_GOVERNANCE_GATE_MISSING'):
                read_explanation(self.c,Missing(),attempt_id=1,question_id=1,student_id=1,owned=self.owned)
    def test_no_fuzzy_unapproved_capsule(self):
        self.c.execute("UPDATE learning_capsules SET review_status='Pending'")
        out=self.explanation()
        self.assertIsNone(out['learning_capsule'])
    def test_source_explanation_missing_denied_without_approved_capsule(self):
        self.c.execute('UPDATE integration_ph_question_version_store SET content_json=?',
                       (json.dumps(dict(CONTENT,marking={'key_type':'NUMERIC','key':'4','explanation':''})),))
        self.c.execute("UPDATE learning_capsules SET review_status='Pending'")
        self.hold('APPROVED_EXPLANATION_NOT_AVAILABLE')
    def test_missing_source_explanation_falls_back_to_exact_capsule(self):
        self.c.execute('UPDATE integration_ph_question_version_store SET content_json=?',
                       (json.dumps(dict(CONTENT,marking={'key_type':'NUMERIC','key':'4','explanation':''})),))
        out=self.explanation()
        self.assertEqual(out['simple_explanation'],'Divide into equal groups.')
    def test_fake_http_flags_cannot_override_approval(self):
        # Only route identity comes from browser; source approvals are server-computed.
        self.c.execute('UPDATE integration_ph_question_version_store SET governance_json=?',
                       (json.dumps(dict(GOV,hold_status='HOLD')),))
        self.hold('ACADEMIC_GOVERNANCE_NOT_READY')
    def test_no_learner_identity_in_view(self):
        value=self.explanation()
        self.assertNotIn('Q11-SYN',json.dumps(value))
        self.assertNotIn('R-UK-SYN',json.dumps(value))
        self.assertNotIn('source',json.dumps(value).lower())

class Overlay(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.p=Path(self.temp.name)
        (self.p/'templates').mkdir()
        (self.p/'.uk11_disposable_qualification_runtime').write_text('synthetic only')
        (self.p/'app.py').write_text("def result(aid):\n    details=c.execute('''SELECT aa.*,q.question,q.answer,q.explanation,q.level,q.subtopic,q.family_id,q.variant,\n    q.learning_outcome FROM attempt_answers aa JOIN questions q ON q.id=aa.question_db_id WHERE aa.attempt_id=?''',(aid,)).fetchall()\n")
        (self.p/'scoremax_production.py').write_text('from written_ai_adapter import install as install_written_ai\ninstall_written_ai(scoremax)\napplication=scoremax.app\napp=application\n')
        (self.p/'templates/result.html').write_text('''{% extends "base.html" %}{% block content %}\n<div class="answer-review">\n  <strong>{{d.question}}</strong><p>{{d.explanation}}</p>\n<a class="question-report-link" href="/report">Report</a>\n</div>\n{% endblock %}\n''')
    def tearDown(self):self.temp.cleanup()
    def test_disposable_runtime_is_required(self):
        (self.p/'.uk11_disposable_qualification_runtime').unlink()
        before=(self.p/'scoremax_production.py').read_text()
        with self.assertRaisesRegex(RuntimeError,'DISPOSABLE_RUNTIME_REQUIRED'):apply(self.p)
        self.assertEqual((self.p/'scoremax_production.py').read_text(),before)
    def test_fails_before_any_write_if_anchor_missing(self):
        p=self.p/'scoremax_production.py';p.write_text('app=application\n')
        before=p.read_text()
        with self.assertRaisesRegex(RuntimeError,'NATIVE_ANCHOR_MISMATCH'):apply(self.p)
        self.assertEqual(before,p.read_text())
        self.assertFalse((self.p/'uk11_result_explanation.py').exists())
    def test_fails_if_native_owner_missing(self):
        p=self.p/'scoremax_production.py';p.write_text('application=scoremax.app\napp=application\n')
        with self.assertRaisesRegex(RuntimeError,'NATIVE_WRITTEN_OWNERSHIP_HOOK_MISSING'):apply(self.p)
        self.assertFalse((self.p/'uk11_result_explanation.py').exists())
    def test_overlay_additive_and_jinja_valid(self):
        out=apply(self.p)
        self.assertFalse(out['default_enabled']);self.assertEqual(out['provider_calls'],0)
        self.assertIn('install_uk11_explanation(scoremax)',(self.p/'scoremax_production.py').read_text())
        text=(self.p/'templates/result.html').read_text()
        self.assertIn(RESULT_MARKER,text)
        self.assertIn('SELECT aa.*,q.ph_market_id,q.ph_is_auto_markable,q.question',(self.p/'app.py').read_text())
        self.assertIn('question-report-link',text)
        from jinja2 import Environment, DictLoader, select_autoescape
        env=Environment(loader=DictLoader({'base.html':'{% block content %}{% endblock %}'}),autoescape=select_autoescape(['html']))
        env.globals.update(url_for=lambda endpoint,**values:'/uk11-safe-route',uk11_explanation_available=lambda:True)
        tpl=env.from_string(text)
        html=tpl.render(d=dict(is_correct=0,selected_answer='B',explanation='<script>bad()</script>',ph_question_id='Q11-SYN',
                               ph_market_id='UK',ph_is_auto_markable=1,marks_awarded=0,question_db_id=1,question='Question',marking_status='AUTO_INCORRECT'),a=dict(id=1))
        self.assertIn('Explain my mistake',html)
        self.assertNotIn('<script>bad()',html)
        for replacement in (dict(is_correct=1),dict(selected_answer=''),dict(ph_market_id='PK'),dict(marking_status='AUTO_UNSCORED'),dict(ph_is_auto_markable=0),dict(marks_awarded=None)):
            d=dict(is_correct=0,selected_answer='B',explanation='Approved',ph_question_id='Q11',ph_market_id='UK',
                   question_db_id=1,question='Question',ph_is_auto_markable=1,marks_awarded=0,marking_status='AUTO_INCORRECT',**{})
            d.update(replacement)
            h=tpl.render(d=d,a={'id':1})
            self.assertNotIn('Explain my mistake',h)
        with self.assertRaisesRegex(RuntimeError,'UK_EXPLANATION_ALREADY_PRESENT'):apply(self.p)
    def test_template_escapes_untrusted_text(self):
        from jinja2 import Environment,DictLoader,select_autoescape
        t=(Path(__file__).parent/'uk11_explain_mistake.html').read_text()
        e=Environment(loader=DictLoader({'base.html':'{% block content %}{% endblock %}'}),autoescape=select_autoescape(['html']))
        h=e.from_string(t).render(explanation={'title':'Explain','simple_explanation':'<script>x</script>',
            'learning_capsule':None,'next_action':'Try again.'},result_url='/result/1')
        self.assertNotIn('<script>x</script>',h);self.assertIn('&lt;script&gt;',h)

class Install(unittest.TestCase):
    def setUp(self):
        class App:
            def __init__(self):
                self.extensions={};self.jinja_env=types.SimpleNamespace(globals={});self.routes={}
            def route(self,path,**kw):
                def decorator(fn):self.routes[path]=fn;return fn
                return decorator
        self.app=App()
        self.native=types.SimpleNamespace(app=self.app,require=lambda role:role=='student',db=lambda:None,
                      integration_v1=FakeIntegration())
    def test_disabled_install_does_not_register(self):
        with patch.dict(os.environ,{FLAG:'0'}):r=install(self.native)
        self.assertEqual(r['routes_registered'],0)
        self.assertFalse(self.app.routes)
        self.assertFalse(self.app.jinja_env.globals['uk11_explanation_available']())
    def test_enabled_requires_existing_native_owner_hook(self):
        with patch.dict(os.environ,{FLAG:'1'}):
            with self.assertRaisesRegex(RuntimeError,'NATIVE_OWNED_MATERIAL'):
                install(self.native)
    def test_integration_routes_are_get_only_and_reused(self):
        self.app.extensions['scoremax_written_ai_owned_material']=lambda *args:None
        # Flask is unavailable in this isolated worker; import a minimal namespace to verify wiring.
        fake=types.ModuleType('flask')
        fake.abort=lambda code: (_ for _ in ()).throw(RuntimeError('HTTP'+str(code)))
        fake.redirect=lambda u:u
        fake.render_template=lambda t,**kw:(t,kw)
        fake.session={'user_id':1}
        fake.url_for=lambda name,**kw:'/result/'+str(kw.get('aid'))
        with patch.dict(sys.modules,{'flask':fake}),patch.dict(os.environ,{FLAG:'1'}):
            r=install(self.native)
            self.assertEqual(r['routes_registered'],1)
            self.assertTrue(any('/uk11/result/' in k for k in self.app.routes))
            self.assertFalse(r['official_score_changes'])
            self.assertFalse(r['mastery_changes'])
            with self.assertRaisesRegex(RuntimeError,'UK_EXPLANATION_ALREADY_INSTALLED'):install(self.native)

if __name__=='__main__':unittest.main()
