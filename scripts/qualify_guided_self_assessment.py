"""Synthetic portability and existing-runtime regression; no academic clearance."""
from pathlib import Path
import argparse
import copy
import json
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'ux_vnext_overlay'))
import guided_self_assessment as guided


def source_fixture():
    return {'Capability_Status':'READY','Required_Produced_Representation':'NONE',
        'Learner_Output_Type':'TEXT_SHORT_RESPONSE','Learner_Question':'[SYNTHETIC] Describe the sample.',
        'Model_Answer':'The sample is rectangular. Its surface is smooth.', 'Marks':3,
        'Mark_Point_Count':2,'Mark_Point_Values':'1;2',
        'Canonical_Accepted_Evidence':'The sample is rectangular. | Its surface is smooth.',
        '_PH_Original_Master_SHA256':'0'*64}


def fixture():
    source = source_fixture()
    rubric = {'version':'PH-SAQ-SCORING-CONTRACT-1','maximum_marks':3,
        'auto_marking_eligibility':'RUBRIC_SEMANTICALLY_SCORABLE','scoring_type':'SEMANTIC_MARK_POINT',
        'required_mark_points':[
            {'id':'p1','description':'The sample is rectangular.','marks':1},
            {'id':'p2','description':'Its surface is smooth.','marks':2}],
        'source_scoring_policies':{'Contradiction_Rule':'A contradiction removes credit for that point.'}}
    rubric['contract_sha256']=guided.digest(rubric)
    bound=guided.bind(rubric,source,{'mode':guided.MODE,'reference':'SYNTHETIC_TEST_ONLY'})
    return {'qtype':'Constructed Response','question':source['Learner_Question'],'answer':source['Model_Answer'],
        'marks':3,'ph_is_auto_markable':0,'question_version':2,'stimulus_data':'','command_word':'describe',
        'answer_config':'{}','marking_config':json.dumps({'auto_markable':False,'marks':3,'rubric':bound})}


class Portable(unittest.TestCase):
    def test_approved_effective_wording_preserves_original_source(self):
        source=source_fixture();before=copy.deepcopy(source);q=fixture()
        rubric=json.loads(q['marking_config'])['rubric'];rubric.pop('guided_self_assessment');rubric.pop('contract_sha256');rubric['contract_sha256']=guided.digest(rubric)
        payload={'stem':'[SYNTHETIC] A student describes the sample.','answer':source['Model_Answer']}
        evidence={'field':'stem','public_id':'SYNTHETIC-APPLIED-AMENDMENT','checksum_sha256':'1'*64,'original_sha256':guided.digest(source['Learner_Question']),'effective_sha256':guided.digest(payload['stem'])}
        bound=guided.bind(rubric,source,{'mode':guided.MODE,'reference':'SYNTHETIC_TEST_ONLY'},learner_payload=payload,amendment_evidence=[evidence])
        marking={'auto_markable':False,'rubric':bound}
        delivery=guided.contract(marking,payload['stem'],payload['answer'],source['Marks'])
        self.assertEqual(source,before);self.assertEqual(delivery['source_row_sha256'],guided.digest(source))
        self.assertEqual(delivery['original_contract_sha256'],rubric['contract_sha256'])
        with self.assertRaises(ValueError):guided.contract(marking,source['Learner_Question'],payload['answer'],source['Marks'])
        for bad in ([],[dict(evidence,original_sha256='0'*64)],[dict(evidence,effective_sha256='0'*64)],[dict(evidence,public_id='')]):
            with self.assertRaises(ValueError):guided.bind(rubric,source,{'mode':guided.MODE,'reference':'SYNTHETIC_TEST_ONLY'},learner_payload=payload,amendment_evidence=bad)

    def test_exact_source_and_original_weight_preserved(self):
        q=fixture();authority=guided.from_question(q);view=guided.guidance(q)
        self.assertEqual(authority['authority'],guided.AUTHORITY)
        self.assertEqual([p['marks'] for p in view['points']],[1,2])
        self.assertEqual(view['model_answer'],q['answer'])
        self.assertNotIn('awarded_marks',json.dumps(view));self.assertNotIn('confidence',json.dumps(view))

    def test_tampering_is_rejected(self):
        for field,value in [('question','changed'),('answer','changed'),('marks',2)]:
            q=fixture();q[field]=value
            with self.assertRaises(ValueError):guided.from_question(q)
        q=fixture();mc=json.loads(q['marking_config']);mc['rubric']['required_mark_points'][0]['marks']=2
        q['marking_config']=json.dumps(mc)
        with self.assertRaises(ValueError):guided.from_question(q)

    def test_scoring_authority_conflict(self):
        for key,value in [('auto_markable',True),('scoring_contract','normalised_text_exact')]:
            q=fixture();mc=json.loads(q['marking_config']);mc[key]=value;q['marking_config']=json.dumps(mc)
            with self.assertRaises(ValueError):guided.from_question(q)

    def test_original_saq_unmodified_and_not_inferred_guided(self):
        q=fixture();mc=json.loads(q['marking_config']);original=copy.deepcopy(mc['rubric'])
        bound=original.pop('guided_self_assessment');original.pop('contract_sha256')
        self.assertEqual(guided.digest(original),bound['original_contract_sha256'])
        original['contract_sha256']=guided.digest(original);mc['rubric']=original;q['marking_config']=json.dumps(mc)
        self.assertIsNone(guided.from_question(q))


def runtime_suite():
    from qualify_assessment_contract_repair import AssessmentRepair,sm
    from unittest.mock import patch
    class Runtime(AssessmentRepair):
        def test_commercial_subject_scope_uses_active_native_memberships(self):
            import commercial_access_engine as coverage
            qid,env=self.ph_fixture()
            subject=self.c.execute('SELECT subject FROM questions WHERE id=?',(qid,)).fetchone()['subject']
            self.assertNotIn(subject,coverage.programme_subjects(self.c,'MDCAT'))
            # Reuse the accepted immutable version in a synthetic active destination.
            release=self.c.execute('SELECT * FROM integration_ph_content_releases').fetchone()
            columns=list(release.keys());values=[release[k] for k in columns]
            values[columns.index('id')]=None
            values[columns.index('release_id')]='SYN-MDCAT-COVERAGE'
            values[columns.index('programme_id')]='MDCAT'
            values[columns.index('chapter_id')]='MDCAT::'+str(release['subject_id']).upper()+'::UNIT::01'
            values[columns.index('local_status')]='STAGED'
            self.c.execute('INSERT INTO integration_ph_content_releases('+','.join(columns)+') VALUES('+','.join('?' for _ in columns)+')',values)
            membership=self.c.execute('SELECT * FROM integration_ph_release_question_membership').fetchone()
            self.c.execute('INSERT INTO integration_ph_release_question_membership(release_id,release_version,question_id,question_version_id,ordinal,admitted_at) VALUES(?,?,?,?,1,CURRENT_TIMESTAMP)',
                ('SYN-MDCAT-COVERAGE',membership['release_version'],membership['question_id'],membership['question_version_id']))
            self.c.commit()
            self.assertNotIn(subject,coverage.programme_subjects(self.c,'MDCAT'))
            self.c.execute("UPDATE integration_ph_content_releases SET local_status='ACTIVE' WHERE release_id='SYN-MDCAT-COVERAGE'");self.c.commit()
            self.assertNotIn(subject,coverage.programme_subjects(self.c,'MDCAT'))
            # ACTIVE alone is not product authority. Exercise the existing
            # exact-checksum authorisation path on this disposable destination.
            self.c.execute("UPDATE integration_ph_content_releases SET local_status='STAGED' WHERE release_id='SYN-MDCAT-COVERAGE'");self.c.commit()
            import scoremax_integration_v1 as integration
            approved=integration.authorize_product_activation(self.c,'SYN-MDCAT-COVERAGE',
                release['release_version'],release['package_checksum_sha256'],'SYNTHETIC-OWNER','Isolated guided coverage regression')
            self.c.commit();self.assertEqual(approved['status'],'ACTIVE',approved)
            self.assertIn(subject,coverage.programme_subjects(self.c,'MDCAT'))
            self.assertNotIn(subject,coverage.programme_subjects(self.c,'FSc Part 2'))

        def test_guided_only_subject_is_discoverable_within_current_programme(self):
            from flask import template_rendered
            qid=self.insert(fixture());contexts=[]
            def capture(sender,template,context,**extra):
                if template.name=='test_setup.html':contexts.append(context)
            with template_rendered.connected_to(capture,sm.app):
                response=self.client.get('/test/setup?response_mode=GUIDED_SELF_ASSESSMENT&scope=full',base_url='https://localhost')
            self.assertEqual(response.status_code,200)
            self.assertIn('Physics',contexts[-1]['subjects'])
            self.assertEqual(contexts[-1]['programmes'],['FSc Part 1'])
            self.assertIn('name="response_mode"',response.text)
            self.assertIn('aria-label="Practice type"',response.text)
            self.assertIn('GUIDED_SELF_ASSESSMENT" selected',response.text)
            self.assertTrue(any(ch['chapter']=='Measurements' for ch in contexts[-1]['chapters']))
            self.c.execute("UPDATE questions SET active=0 WHERE id=?",(qid,));self.c.commit()
            with template_rendered.connected_to(capture,sm.app):
                self.client.get('/test/setup?response_mode=GUIDED_SELF_ASSESSMENT',base_url='https://localhost')
            self.assertNotIn('Physics',contexts[-1]['subjects'])

        def test_guided_existing_practice_builder(self):
            qid=self.insert(fixture())
            self.c.execute("UPDATE questions SET level='Foundation' WHERE id=?",(qid,));self.c.commit()
            for scope in ('full','chapter','half','multi'):
                form={'_csrf_token':'synthetic-csrf','response_mode':guided.MODE,'programme':'FSc Part 1',
                    'subject':'Physics','scope':scope,'count':'1','mode':'practice','chapter':'Measurements','chapters':'Measurements'}
                response=self.client.post('/test/start',data=form,base_url='https://localhost')
                self.assertEqual(response.status_code,302)
                self.assertRegex(response.location,r'/test/session/\d+$')
                aid=int(response.location.rsplit('/',1)[-1])
                row=self.c.execute('SELECT * FROM assessment_sessions WHERE id=?',(aid,)).fetchone()
                self.assertEqual(sm.parse_ids(row['question_ids']),[qid])
                self.assertFalse(json.loads(row['meta_json']).get('blueprint_snapshot'))
            for extras in ({'mode':'mock'},{'mcq_only':'1'},{'question_type':'MCQ'}):
                self.assertEqual(self.client.post('/test/start',data=dict(form,**extras),base_url='https://localhost').status_code,409)
        def test_delayed_save_cannot_overwrite_submitted_response(self):
            qid=self.insert(fixture())
            aid=sm.create_assessment_session(self.c,self.uid,'practice',None,[qid],
                {'programme':'FSc Part 1','response_mode':guided.MODE})
            self.post(aid,{'answer':'Frozen original response'})
            original=sm.save_assessment;fired=[]
            def delayed_save(*args,**kwargs):
                if not fired:
                    fired.append(True)
                    self.assertEqual(self.submit(aid).status_code,302)
                return original(*args,**kwargs)
            with patch.object(sm,'save_assessment',side_effect=delayed_save):
                response=self.post(aid,{'answer':'Late concurrent replacement'})
            self.assertEqual(response.status_code,409)
            self.assertEqual(self.saved(aid),{str(qid):'Frozen original response'})
            self.assertEqual(self.client.get(f'/test/session/{aid}/guidance',base_url='https://localhost').status_code,200)
            self.assertIsNone(self.attempt(aid))

        def test_guided_complete_unscored_journey(self):
            q=fixture();qid=self.insert(q)
            aid=sm.create_assessment_session(self.c,self.uid,'practice',None,[qid],
                {'programme':'FSc Part 1','response_mode':guided.MODE})
            url=f'/test/session/{aid}'
            self.assertEqual(self.client.get(url+'/guidance',base_url='https://localhost').status_code,404)
            self.assertNotIn(q['answer'],self.client.get(url,base_url='https://localhost').text)
            with patch.object(sm,'mark_question_result',side_effect=AssertionError('NO_MARKER')):
                self.post(aid,{'answer':'My own description'});self.assertEqual(self.submit(aid).status_code,302)
            self.assertIsNone(self.attempt(aid))
            self.assertIn(q['answer'],self.client.get(url+'/guidance',base_url='https://localhost').text)
            form={'_csrf_token':'synthetic-csrf','review_0_0':'demonstrated','review_0_1':'unsure'}
            self.assertEqual(self.client.post(url+'/guidance',data=form,base_url='https://localhost').status_code,200)
            self.assertEqual(self.client_for('syn-2').get(url+'/guidance',base_url='https://localhost').status_code,404)
            reply=self.client.post(url+'/retry',data={'_csrf_token':'synthetic-csrf'},base_url='https://localhost')
            self.assertEqual(reply.status_code,302)
            self.assertEqual(self.saved(aid),{str(qid):'My own description'})
            self.assertEqual(self.c.execute('SELECT COUNT(*) FROM attempts').fetchone()[0],0)
        def test_guided_denied_scored_and_wrong_programme(self):
            qid=self.insert(fixture())
            with self.assertRaises(sm.question_contracts.QuestionContractError):self.start([qid])
            for mode,programme in [('mock','FSc Part 1'),('exam','FSc Part 1'),('practice','MDCAT')]:
                with self.assertRaises(sm.question_contracts.QuestionContractError):
                    sm.create_assessment_session(self.c,self.uid,mode,None,[qid],{'programme':programme,'response_mode':guided.MODE})
    return unittest.TestSuite(Runtime(name) for name in Runtime.__dict__ if name.startswith('test_'))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--portable',action='store_true');parser.add_argument('--report',default='guided_qualification.json');args=parser.parse_args()
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Portable)
    if not args.portable:suite.addTests(runtime_suite())
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    Path(args.report).write_text(json.dumps({'passed':result.wasSuccessful(),'tests':result.testsRun,
        'failures':[{'test':str(t),'trace':e} for t,e in result.failures+result.errors],
        'synthetic_only':True,'production_mutations':False},indent=2))
    raise SystemExit(not result.wasSuccessful())
