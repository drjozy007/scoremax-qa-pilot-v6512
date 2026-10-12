"""Use existing admission and persisted learner-result paths in disposable DBs."""
import copy,json,unittest
from qualify_written_entrypoints import WrittenEntryPoints,sm
from qualify_pr174_admission_boundary import PR174AdmissionBoundary,integration
from qualify_native_adaptive_chemistry import ROWS,compiled,source_contract

class AdaptivePersistence(WrittenEntryPoints):
    def attempt(self,key,answer):
        row=ROWS[key];rubric=copy.deepcopy(compiled(key)['rubric'])
        qid,pid=self.written({**rubric,'question_id':row['Question_ID'],'question_family_id':'CHEM-TEST',
            'question_type':'SHORT_RESPONSE','command_verb':'state'})
        aid=self.c.execute("""INSERT INTO written_attempts(student_id,written_question_id,package_id,attempt_mode,
          entry_method,evidence_type,support_level,novelty_status,status,maximum_mark,package_version,rubric_version)
          VALUES(?,?,?,'practice','typed','independent_production','independent','seen_family','SUBMITTED',1,'1','NATIVE-1')""",(self.uid,qid,pid)).lastrowid
        vid=self.c.execute("""INSERT INTO written_answer_versions(attempt_id,version_no,version_type,answer_text,word_count,is_frozen)
          VALUES(?,1,'ORIGINAL_TYPED',?,?,0)""",(aid,answer,len(answer.split()))).lastrowid
        self.c.commit();return aid,vid

    def test_adaptive_correct_persistence_and_replay(self):
        aid,vid=self.attempt('Q012','n=PV/(RT)')
        first=sm.written_evaluate_attempt(self.c,aid,vid);self.c.commit()
        result,run=first;self.assertEqual(result['proposed_mark'],1);self.assertIsNotNone(run)
        before=self.counts();self.assertEqual(sm.written_evaluate_attempt(self.c,aid,vid),first);self.assertEqual(self.counts(),before)
        self.assertEqual(self.c.execute('SELECT current_mark FROM written_attempts WHERE id=?',(aid,)).fetchone()[0],1)
        self.assertEqual(self.counts()['written_exemplar_candidates'],0)

    def test_adaptive_abstention_has_no_mastery_or_human_task(self):
        aid,vid=self.attempt('Q012','PV=nRT. PV=nT.')
        result,run=sm.written_evaluate_attempt(self.c,aid,vid);self.c.commit()
        self.assertIsNone(result['proposed_mark']);self.assertIsNone(run)
        row=self.c.execute('SELECT current_mark,status FROM written_attempts WHERE id=?',(aid,)).fetchone()
        self.assertIsNone(row['current_mark']);self.assertEqual(row['status'],'AUTO_UNSCORED')
        for table in ['written_marking_runs','written_mark_point_results','written_mastery_evidence','written_recovery_tasks','written_exemplar_candidates']:
            self.assertEqual(self.counts()[table],0,table)

    def test_adaptive_explicit_contradiction_persists_zero(self):
        aid,vid=self.attempt('Q062','Condensation. Evaporation.')
        result,run=sm.written_evaluate_attempt(self.c,aid,vid);self.c.commit()
        self.assertEqual(result['proposed_mark'],0);self.assertIsNotNone(run)
        self.assertEqual(self.c.execute('SELECT current_mark FROM written_attempts WHERE id=?',(aid,)).fetchone()[0],0)

class AdaptiveAdmission(PR174AdmissionBoundary):
    def test_adaptive_three_real_contracts_native_admission(self):
        for i,key in enumerate(['Q012','Q013','Q062']):
            if i:self.tearDown();self.setUp()
            row=ROWS[key];e=self.constructed('SHORT_RESPONSE',source_contract(row));q=e['payload']['questions'][0]
            q['content'].pop('response_contract',None);q['content']['marking'].pop('scoring_contract',None)
            q['content'].update(stem=row['Learner_Question'],command_word='')
            q['content']['marking'].update(key=row['Model_Answer'],marks=row['Marks'],accepted_answers=[row['Model_Answer']])
            self.rehash(e);receipt=self.admit(e);version=self.qversion(e)
            self.assertEqual(receipt['status'],'ACCEPTED');self.assertEqual(self.admit(e,200)['receipt_id'],receipt['receipt_id'])
            projection=integration.effective_projection(json.loads(version['scoremax_projection_json']),json.loads(version['content_json']))
            actual=integration.question_contracts.validate_assessment_contract(projection)['constructed_contract']
            self.assertEqual(actual,compiled(key))
            self.assertEqual(self.c.execute('SELECT count(*) FROM integration_ph_product_activation_authorizations').fetchone()[0],0)
            self.assertEqual(self.c.execute('SELECT local_status FROM integration_ph_content_releases').fetchone()[0],'STAGED')

    def test_adaptive_unqualified_semantics_rejected_before_writes(self):
        row=ROWS['Q001'];e=self.constructed('SHORT_RESPONSE',source_contract(row));q=e['payload']['questions'][0]
        q['content'].pop('response_contract',None);q['content']['marking'].pop('scoring_contract',None)
        q['content'].update(stem=row['Learner_Question']);q['content']['marking'].update(key=row['Model_Answer'],marks=2)
        self.rehash(e);self.admit(e,422);self.assert_empty_staging()

if __name__=='__main__':
    suite=unittest.TestSuite(cls(n) for cls in [AdaptivePersistence,AdaptiveAdmission] for n in dir(cls) if n.startswith('test_adaptive_'))
    r=unittest.TextTestRunner(verbosity=2).run(suite)
    print('ADAPTIVE_ROUTES',json.dumps({'tests':r.testsRun,'passed':r.wasSuccessful(),'production_mutated':False}))
    raise SystemExit(not r.wasSuccessful())
