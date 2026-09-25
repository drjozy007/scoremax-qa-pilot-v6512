"""No new PH schema/columns: verify existing programme scope and authority fences.

Reuses isolated native WSGI/PH fixture helpers. These are representative synthetic
contracts, not a replay of real Cross50 source bytes or a new academic qualification.
"""
from __future__ import annotations
import argparse,copy,hashlib,json,unittest
from datetime import datetime,timezone
from pathlib import Path
from qualify_assessment_contract_repair import AssessmentRepair,ROOT,sm,integration,reviewer,RUBRIC

DETAILS=[]
class ExistingPHCompatibility(unittest.TestCase):
    def setUp(self):
        self.case=AssessmentRepair('test_native_eight_response_journeys')
        self.case._testMethodName=self._testMethodName
        self.case.setUp();self.c=self.case.c
    def tearDown(self):self.case.tearDown()
    def envelope(self,version='1.2.0',programme='FSc / Intermediate',grade='12',display=None):
        e=json.loads((ROOT/'integration_examples/PH_SM_APPROVED_CONTENT_V1.example.json').read_text())
        stamp=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
        tag=self._testMethodName+'::'+version
        e.update(schema_version=version,message_id='SYN-MSG::'+tag,idempotency_key='SYN-IDEM::'+tag,occurred_at=stamp,sent_at=stamp)
        p=e['payload'];r=p['release'];q=p['questions'][0]
        q.update(question_id='SYN-PH::'+tag,question_version_id='SYN-PHV::'+tag,question_version_number=1,supersedes_question_version_id=None,effective_from=stamp)
        r.update(release_id='SYN-RELEASE::'+tag,release_version='1',generated_at=stamp,effective_at=stamp,programme_id=programme)
        q['curriculum'].update(programme_id=programme,grade_year_id=grade)
        q['curriculum']['display'].update(programme=programme if display is None else display,grade_year=grade)
        if version!='1.0.0':
            p['release_operation']='PUBLISH_SNAPSHOT';r.update(withdrawn_at=None,withdrawal_reason=None)
        if version=='1.3.0':
            p['release_operation']='STAGE_FOR_DELIVERY_QA';r.update(release_status='DELIVERY_QA_ONLY',effective_at=None)
            q['architecture'].update(knowledge_node_ids=[],claim_family_id=None,reasoning_seed_id=None,evidence_role=None,
              independent_mastery_eligible=False,independent_mastery_weight=0,mastery_status='PENDING_CONTRACT',mastery_level=None,mastery_ceiling=None)
            q['governance'].update(academic_review_state='QA_CANDIDATE',hold_status='QA_ONLY',source_check_status='QA_ONLY',
              release_readiness='NOT_AUTHORIZED',rights_status='OWNED',generated_clearance_status='NOT_APPLICABLE',
              release_authority_conferred=False,mastery_authority_conferred=False)
        return self.rehash(e)
    def rehash(self,e):
        for q in e['payload']['questions']:q['question_checksum_sha256']=integration._object_checksum(q,'question_checksum_sha256')
        e['payload_checksum_sha256']=integration.payload_checksum(e['payload']);return e
    def admit(self,e,expected=202):
        before=copy.deepcopy(e)
        receipt,status=integration.admit_content_envelope(self.c,e,e['payload_checksum_sha256']);self.c.commit()
        self.assertEqual(status,expected,receipt);self.assertEqual(e,before)
        return receipt
    def activate(self,e):
        r=e['payload']['release'];out=integration.authorize_product_activation(self.c,r['release_id'],r['release_version'],r['package_checksum_sha256'],'SYNTHETIC-OWNER','Isolated existing-contract regression')
        self.c.commit();return out
    def qversion(self,e):
        return self.c.execute('SELECT * FROM integration_ph_question_version_store WHERE question_id=?',(e['payload']['questions'][0]['question_id'],)).fetchone()
    def test_all_existing_content_schema_versions_preserved(self):
        for version in ('1.0.0','1.1.0','1.2.0','1.3.0'):
            with self.subTest(version=version):
                e=self.envelope(version);self.admit(e);v=self.qversion(e)
                projection=json.loads(v['scoremax_projection_json'])
                self.assertEqual(projection['programme'],'FSc Part 2')
                self.assertEqual(projection['ph_programme_id'],'FSc / Intermediate')
                self.assertEqual(json.loads(v['curriculum_json']),e['payload']['questions'][0]['curriculum'])
                self.assertEqual(json.loads(v['content_json']),e['payload']['questions'][0]['content'])
                self.assertEqual(v['question_checksum_sha256'],e['payload']['questions'][0]['question_checksum_sha256'])
                DETAILS.append({'existing_schema':version,'accepted':True,'original_curriculum_and_content_preserved':True,'learner_programme':'FSc Part 2'})
    def test_generic_scope_and_known_grade_uses_existing_information(self):
        for name in ('FSc / Intermediate','FSc','HSSC','Intermediate'):
            for grade in ('11','12','Year 11','Grade 12','YEAR_11'):
                curriculum={'programme_id':name,'grade_year_id':grade,'display':{'programme':name}}
                expected='FSc Part 1' if '11' in grade else 'FSc Part 2'
                self.assertEqual(sm.question_contracts.programme_from_curriculum(curriculum),expected)
    def test_grade_from_existing_display_is_sufficient(self):
        cur={'programme_id':'FSc / Intermediate','display':{'grade_year':'Grade 12'}}
        self.assertEqual(sm.question_contracts.programme_from_curriculum(cur),'FSc Part 2')
    def test_existing_specific_programme_needs_no_new_grade(self):
        for token in ('FSC_PART_II','FSc Part II','HSSC-II','FSc Part 2'):
            self.assertEqual(sm.question_contracts.programme_from_curriculum({'programme_id':token}),'FSc Part 2')
    def test_shared_reader_aliases_match_projection(self):
        for expected,aliases in sm.question_contracts._programme_alias_groups().items():
            for alias in aliases:
                self.assertEqual(sm.canonical_programme(alias),expected)
                self.assertIn(alias,sm._programme_aliases(expected))
        self.assertEqual(sm._programme_aliases(''),[])
    def test_mdcat_does_not_become_fsc_due_to_school_grade(self):
        for grade in ('11','12',None):
            self.assertEqual(sm.question_contracts.programme_from_curriculum({'programme_id':'MDCAT','grade_year_id':grade}),'MDCAT')
    def test_unknown_curriculum_remains_unchanged(self):
        self.assertEqual(sm.question_contracts.programme_from_curriculum({'programme_id':'UNRELATED::OPAQUE','grade_year_id':'12'}),'UNRELATED::OPAQUE')
        self.assertEqual(sm.question_contracts.programme_from_curriculum({}), '')
    def test_ambiguous_fsc_year_is_validation_receipt_not_default_or_500(self):
        e=self.envelope(grade=None);receipt=self.admit(e,422)
        self.assertIn('FSC_YEAR_UNRESOLVED',{x['code'] for x in receipt['errors']})
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM integration_ph_question_version_store').fetchone()[0],0)
    def test_conflicting_year_fields_are_not_silently_resolved(self):
        e=self.envelope();e['payload']['questions'][0]['curriculum']['display']['grade_year']='11';self.rehash(e)
        r=self.admit(e,422);self.assertIn('PROGRAMME_YEAR_CONFLICT',{x['code'] for x in r['errors']})
    def test_conflicting_programmes_return_validation_receipt(self):
        e=self.envelope(programme='FSC_PART_II',display='MDCAT');self.rehash(e)
        r=self.admit(e,422);self.assertIn('PROGRAMME_CONTEXT_CONFLICT',{x['code'] for x in r['errors']})
    def test_specific_fsc_year_mismatch_is_not_an_alias(self):
        e=self.envelope(programme='FSC_PART_II',grade='11');r=self.admit(e,422)
        self.assertIn('PROGRAMME_YEAR_CONFLICT',{x['code'] for x in r['errors']})
    def test_staged_and_new_assessment_share_same_year_without_source_rewrite(self):
        e=self.envelope();self.admit(e);before=dict(self.qversion(e))
        mid=self.c.execute('SELECT id FROM integration_ph_release_question_membership').fetchone()[0]
        staged=reviewer._staged_question(self.c,mid);self.assertEqual(staged['programme'],'FSc Part 2')
        self.assertEqual(self.activate(e)['status'],'ACTIVE')
        q=self.c.execute('SELECT * FROM questions').fetchone();self.assertEqual(q['programme'],'FSc Part 2')
        aid=sm.create_assessment_session(self.c,self.case.uid,'practice',None,[q['id']],{'programme':'FSc Part 2','subject':'Chemistry','assessment_kind':'synthetic_regression'})
        session=self.c.execute('SELECT * FROM assessment_sessions WHERE id=?',(aid,)).fetchone()
        pinned=integration.pinned_question(session,q['id'],q)
        self.assertEqual(pinned['programme'],'FSc Part 2');self.assertEqual(pinned['ph_programme_id'],'FSc / Intermediate')
        self.assertEqual(self.case.post(aid,{'answer':'B'}).status_code,302);self.assertEqual(self.case.submit(aid).status_code,302)
        attempt=self.case.attempt(aid);self.assertEqual(attempt['score'],100);self.assertEqual(attempt['programme'],'FSc Part 2')
        self.assertEqual(len(sm.learner_answer_evidence(self.c,self.case.uid,'FSc Part 2')),1)
        self.assertEqual(len(sm.learner_answer_evidence(self.c,self.case.uid,'FSc Part 1')),0)
        self.assertEqual(len(sm.learner_answer_evidence(self.c,self.case.uid,'MDCAT')),0)
        after=dict(self.qversion(e))
        for k in ('content_json','curriculum_json','scoremax_projection_json','question_checksum_sha256'):
            self.assertEqual(before[k],after[k],k)
    def test_legacy_stored_projection_uses_its_existing_curriculum_snapshot(self):
        e=self.envelope();q=e['payload']['questions'][0];stored=integration._projection(q,{})
        stored['programme']='FSc / Intermediate';saved=copy.deepcopy(stored)
        effective=integration.effective_projection(stored,q['content'])
        self.assertEqual(effective['programme'],'FSc Part 2');self.assertEqual(stored,saved)
    def test_started_assessment_context_does_not_change_retroactively(self):
        e=self.envelope();self.admit(e);self.activate(e);q=self.c.execute('SELECT * FROM questions').fetchone()
        aid=sm.create_assessment_session(self.c,self.case.uid,'practice',None,[q['id']],{'programme':'FSc Part 2'})
        session=self.c.execute('SELECT * FROM assessment_sessions WHERE id=?',(aid,)).fetchone();pins=session['ph_question_pins_json']
        self.c.execute("UPDATE questions SET programme='FSc Part 1' WHERE id=?",(q['id'],));self.c.commit()
        current=self.c.execute('SELECT * FROM questions WHERE id=?',(q['id'],)).fetchone()
        self.assertEqual(integration.pinned_question(session,q['id'],current)['programme'],'FSc Part 2')
        self.assertEqual(session['ph_question_pins_json'],pins)
    def test_qa_without_mastery_metadata_is_accepted_but_cannot_activate(self):
        e=self.envelope('1.3.0');q=e['payload']['questions'][0]
        q['curriculum'].update(topic_id=None,subtopic_id=None,learning_outcome_ids=[],teaching_learning_outcome_ids=[])
        q['curriculum']['display'].update(topic=None,subtopic=None,outcome_text=None)
        self.rehash(e);self.admit(e)
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM questions').fetchone()[0],0)
        self.assertNotEqual(self.activate(e)['status'],'ACTIVE')
        self.assertEqual(integration._activate_release(self.c,e['payload']['release']['release_id'],'1'),0)
        self.assertEqual(json.loads(self.qversion(e)['architecture_json'])['knowledge_node_ids'],[])
    def test_replay_preserves_exact_question_version_and_receipt(self):
        e=self.envelope();r=self.admit(e);v=dict(self.qversion(e));again=self.admit(e,200)
        self.assertEqual(r['receipt_id'],again['receipt_id']);self.assertEqual(v,dict(self.qversion(e)))
    def test_version_checksum_conflict_cannot_replace_original(self):
        e=self.envelope();self.admit(e);v=dict(self.qversion(e));e['message_id']+='::conflict';e['idempotency_key']+='::conflict'
        e['payload']['questions'][0]['content']['stem']='Changed source with reused version';self.rehash(e)
        self.admit(e,409);self.assertEqual(v,dict(self.qversion(e)))
    def test_original_structured_rubric_survives_existing_transfer(self):
        e=self.envelope();q=e['payload']['questions'][0]
        q['content'].update(question_family_type='SHORT_RESPONSE',exam_question_type='SHORT_RESPONSE',options=[])
        q['content']['marking'].update(key_type='RUBRIC_ONLY',key=None,accepted_answers=[],marks=2,rubric=copy.deepcopy(RUBRIC))
        self.rehash(e);self.admit(e);p=json.loads(self.qversion(e)['scoremax_projection_json'])
        self.assertEqual(json.loads(p['marking_config'])['rubric'],RUBRIC)
        self.assertEqual(self.activate(e)['status'],'ACTIVE')
    def test_missing_rubric_is_not_manufactured_by_compatibility(self):
        e=self.envelope('1.3.0');q=e['payload']['questions'][0]
        q['content'].update(question_family_type='SHORT_RESPONSE',exam_question_type='SHORT_RESPONSE',options=[])
        q['content']['marking'].update(key_type='TEXT',key='Repeated molecular collisions cause irregular motion.',accepted_answers=[],rubric=None)
        self.rehash(e);self.admit(e)
        v=self.qversion(e);p=integration.effective_projection(json.loads(v['scoremax_projection_json']),json.loads(v['content_json']))
        self.assertIsNone(json.loads(p['marking_config']).get('rubric'))
        with self.assertRaisesRegex(sm.question_contracts.QuestionContractError,'SELF_MARKING_CONTRACT_REQUIRED'):
            sm.question_contracts.validate_assessment_contract(p)
        self.assertNotEqual(self.activate(e)['status'],'ACTIVE')
    def test_existing_transport_schema_bytes_unchanged(self):
        # Commitments from the already-qualified ea5e282 runtime, not this candidate.
        expected={'integration_contracts/PH_SM_APPROVED_CONTENT_V1.schema.json': '77c545d4052eb99f80d28a884676f74442d10ed922269455fe6d9c1a79aa36ab', 'integration_contracts/v1_1_0/PH_SM_APPROVED_CONTENT_V1.schema.json': '6e284757464b63633d4b7c56ca4324fef3c8d7e6ae06daa54753a94657f56078', 'integration_contracts/v1_2_0/PH_SM_APPROVED_CONTENT_V1.schema.json': '053e628091b15c12406bea2b7959f1d8d42f31a3c99b7ab2c2dd765105c63517', 'integration_contracts/v1_3_0/PH_SM_APPROVED_CONTENT_V1.schema.json': '847fa57b07a08a088306d4f01da004882e21a077ea0016e4d77325a452a74936'}
        for name,wanted in expected.items():
            self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),wanted,name)
        if BASELINE:
            for f in sorted((Path(BASELINE)/'integration_contracts').rglob('*.json')):
                self.assertEqual(f.read_bytes(),(ROOT/f.relative_to(BASELINE)).read_bytes(),str(f))

BASELINE=None
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--report',default='existing_ph_compatibility.json');parser.add_argument('--baseline-runtime');args=parser.parse_args();BASELINE=args.baseline_runtime
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ExistingPHCompatibility))
    report={'suite':'EXISTING_PH_COMPATIBILITY_V1','tests_run':result.testsRun,'passed':result.wasSuccessful(),'failures':len(result.failures),'errors':len(result.errors),
      'details':DETAILS,'scope':'Synthetic existing 1.0/1.1/1.2/1.3 contracts on native receiver; not actual Cross50 replay.',
      'transport_schema_changed':False,'new_required_workbook_columns':0,'production_mutation':False,'scoremax_send':False,'bulk_import_authorized':False,
      'source_hashes':{str(f):hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in ('app.py','scoremax_integration_v1.py','question_contract_engine.py')}}
    Path(args.report).write_text(json.dumps(report,indent=2)+'\n');print('EXISTING_PH_COMPATIBILITY_RESULT='+json.dumps(report,sort_keys=True));raise SystemExit(0 if result.wasSuccessful() else 1)
