"""Scoped programme and policy regression on isolated native production startup.

Reuses the previous native assessment fixture. All credentials/data are synthetic;
its import blocks outbound sockets and allocates an isolated temporary database.
"""
from __future__ import annotations
import argparse,copy,hashlib,json,math,os,sqlite3,unittest
from pathlib import Path
from unittest.mock import patch
from qualify_assessment_contract_repair import AssessmentRepair,sm,integration,question,ROOT,BASE,SNAPSHOT
import ux_student_batch as ux
import ux_mastery_rigor_admin as admin_runtime

class ProgrammeMasteryRepair(unittest.TestCase):
    setUp=AssessmentRepair.setUp
    tearDown=AssessmentRepair.tearDown
    insert=AssessmentRepair.insert
    start=AssessmentRepair.start
    post=AssessmentRepair.post
    submit=AssessmentRepair.submit
    attempt=AssessmentRepair.attempt
    client_for=AssessmentRepair.client_for
    saved=AssessmentRepair.saved
    ph_fixture=AssessmentRepair.ph_fixture

    def switch(self,programme,academic=None):
        self.c.execute('UPDATE users SET active_programme=? WHERE id=?',(programme,self.uid))
        if academic:self.c.execute('UPDATE users SET academic_level=? WHERE id=?',(academic,self.uid))
        self.c.commit()
    def programme(self):return self.c.execute('SELECT active_programme FROM users WHERE id=?',(self.uid,)).fetchone()[0]
    def snapshot(self,table):return [dict(r) for r in self.c.execute('SELECT * FROM '+table+' ORDER BY 1')]
    def scoped_question(self,programme='FSc Part 1',subject='Physics',chapter='Measurements',nodes=None,level='Exam Ready'):
        qid=self.insert(question())
        self.c.execute('UPDATE questions SET programme=?,qualification=?,subject=?,chapter=?,level=?,ph_knowledge_node_ids_json=? WHERE id=?',
            (programme,programme,subject,chapter,level,json.dumps(nodes or []),qid));self.c.commit()
        return qid
    def answer_one(self,programme='FSc Part 1',correct=True,subject='Physics',chapter='Measurements'):
        qid=self.scoped_question(programme,subject,chapter)
        meta={'programme':programme,'subject':subject,'chapters':chapter,'scope':'chapter','assessment_kind':'synthetic_regression'}
        aid=sm.create_assessment_session(self.c,self.uid,'practice',None,[qid],meta)
        self.assertEqual(self.post(aid,{'answer':'B' if correct else 'A'}).status_code,302)
        self.assertEqual(self.submit(aid).status_code,302)
        return qid,aid,dict(self.attempt(aid))
    def master_record(self,programme='FSc Part 1',subject='Physics',chapter='Measurements',level='Exam Ready',status='Verified'):
        key=sm.mastery_scope_key('chapter',programme,subject,chapter)
        rid=self.c.execute("""INSERT INTO mastery_records(student_id,scope_type,scope_key,programme,subject,chapter,mastery_level,status,verified_at,verification_due_at)
          VALUES(?,'chapter',?,?,?,?,?,?,'2026-09-01','2099-01-01')""",(self.uid,key,programme,subject,chapter,level,status)).lastrowid
        self.c.commit();return rid
    def policy(self,kind='global',key='',standard=90,rigor=50,status='DRAFT',version=None,evidence=None):
        n=self.c.execute('SELECT COUNT(*) FROM assessment_assembly_policies').fetchone()[0]
        pid=self.c.execute("""INSERT INTO assessment_assembly_policies(policy_code,policy_version,scope_type,scope_key,name,rigor_score,mastery_standard_score,status,evidence_config_json)
          VALUES(?,?,?,?,?,?,?,?,?)""",(f'SYN-P{n}',str(version or n+1),kind,key,'Synthetic policy',rigor,standard,status,json.dumps(evidence or {}))).lastrowid
        self.c.commit();return pid
    def activate(self,pid,reason='Synthetic qualification change'):
        return self.client_for('admin').post(f'/admin/assessment-policies/{pid}/activate',
            data={'_csrf_token':'synthetic-csrf','reason':reason},base_url='https://localhost')
    def status(self,rid):return self.c.execute('SELECT status FROM mastery_records WHERE id=?',(rid,)).fetchone()[0]
    def coverage(self,programme='FSc Part 1',subject='Physics',chapter='Measurements',n=4,mandatory=None):
        source='SYN-CURRICULUM-'+programme+'-'+subject+'-'+chapter
        self.c.execute("INSERT OR IGNORE INTO universal_source_documents(source_id,title,version,file_hash,status,created_at) VALUES(?,?,'1',?,'APPROVED',CURRENT_TIMESTAMP)",(source,'Synthetic curriculum','a'*64))
        ids=[source+f'-N{i}' for i in range(n)]
        for nid in ids:
            self.c.execute("""INSERT OR IGNORE INTO universal_knowledge_nodes(knowledge_node_id,claim_family_id,programme,subject,chapter,claim,source_id,version,status,environment,exam_mastery_eligible,created_at,updated_at)
              VALUES(?,?,?,?,?,?,?,'1','APPROVED','LIVE',1,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)""",(nid,nid+'-CLAIM',programme,subject,chapter,'Synthetic claim',source))
        cfg={'schema':'SM-CURRICULUM-COVERAGE-1','authority':'POWER_HOUSE','complete':True,'source_id':source,'curriculum_version':'1','source_checksum_sha256':'a'*64,
          'programme':programme,'subject':subject,'chapter':chapter,'scope_type':'chapter','required_node_ids':ids,'mandatory_node_ids':[ids[i] for i in (mandatory or [])]}
        row=self.c.execute("SELECT * FROM assessment_assembly_policies WHERE status='ACTIVE' AND scope_type='global'").fetchone()
        evidence=json.loads(row['evidence_config_json'] or '{}');evidence.setdefault('curriculum_coverage_contracts',[]).append(cfg)
        self.c.execute('UPDATE assessment_assembly_policies SET evidence_config_json=? WHERE id=?',(json.dumps(evidence),row['id']));self.c.commit()
        return cfg
    def form_history(self,programme='FSc Part 1',complete=True,passed=1):
        qid,aid,attempt=self.answer_one(programme)
        metadata={'mastery_breadth_ratio':.9,'mastery_target_band_ratio':.5,'mastery_mandatory_covered':True} if complete else {}
        self.c.execute('UPDATE assessment_sessions SET meta_json=? WHERE id=?',(json.dumps(metadata),aid))
        key=sm.mastery_scope_key('chapter',programme,'Physics','Measurements')
        rid=self.c.execute("""INSERT INTO mastery_form_results(student_id,assessment_session_id,attempt_id,scope_type,scope_key,programme,subject,chapter,target_level,score,question_count,passed,demo_only,breadth_ok,unseen_family_ratio)
          VALUES(?,?,?,'chapter',?,?,'Physics','Measurements','Exam Ready',90,20,?,0,1,.9)""",(self.uid,aid,attempt['id'],key,programme,passed)).lastrowid
        self.c.commit();return rid
    def configure_small_mastery(self):
        self.c.execute("UPDATE mastery_policies SET min_forms=1,min_questions=5,min_accuracy=80,target_band_pct=.4,unseen_family_pct=.6,min_breadth_pct=.75 WHERE mastery_level='Exam Ready'")
        self.c.execute("UPDATE users SET access_override_code='full_access' WHERE id=?",(self.uid,));self.c.commit()
    def create_mastery_bank(self,cfg):
        return [self.scoped_question(nodes=[cfg['required_node_ids'][i%len(cfg['required_node_ids'])]]) for i in range(10)]
    def new_mastery_session(self):
        chosen,meta=sm.build_mastery_form(self.c,self.uid,'chapter','Exam Ready','FSc Part 1','Physics','Measurements')
        aid=sm.create_assessment_session(self.c,self.uid,'practice',None,[q['id'] for q in chosen],meta)
        self.c.execute('UPDATE assessment_sessions SET saved_answers=? WHERE id=?',(json.dumps({str(q['id']):'B' for q in chosen}),aid));self.c.commit()
        return chosen,meta,aid

    def test_fsc2_subject_cards_preserve_explicit_year(self):
        self.switch('FSc Part 2','FSc Part 1')
        for subject in ('Physics','Chemistry','Biology'):
            with self.subTest(subject=subject):
                r=self.client.get('/student/subject/'+subject,base_url='https://localhost',follow_redirects=True)
                self.assertEqual(r.status_code,200)
                self.assertEqual(self.programme(),'FSc Part 2')
                self.assertEqual(ux._active_programme_for_student(self.c,self.uid),'FSc Part 2')
    def test_fsc1_subject_cards_do_not_restore_academic_year2(self):
        self.switch('FSc Part 1','FSc Part 2')
        self.assertEqual(self.client.get('/student/subject/Physics',base_url='https://localhost',follow_redirects=True).status_code,200)
        self.assertEqual(self.programme(),'FSc Part 1')
    def test_mdcat_legacy_science_links_preserve_programme(self):
        self.switch('MDCAT','FSc Part 1')
        r=self.client.get('/student/subject/Physics',base_url='https://localhost',follow_redirects=True)
        self.assertEqual(r.status_code,200);self.assertEqual(self.programme(),'MDCAT')
    def test_explicit_catalogue_transition_is_still_available(self):
        self.switch('MDCAT')
        r=self.client.get('/student/catalogue/year12/Physics',base_url='https://localhost',follow_redirects=True)
        self.assertEqual(r.status_code,200);self.assertEqual(self.programme(),'FSc Part 2')
    def test_programme_aliases_do_not_collapse_years(self):
        self.assertEqual(sm.canonical_programme('HSSC-II'),'FSc Part 2')
        self.assertNotIn('Grade 10',sm._programme_aliases('Grade 9'))
        self.assertEqual(sm._programme_scope_sql([]),('0=1',[]))
        with self.assertRaises(ValueError):sm._programme_scope_sql(['MDCAT'],'q;DROP TABLE users')
    def test_populated_programme_wins_over_contradictory_qualification(self):
        qid=self.scoped_question('MDCAT')
        self.c.execute("UPDATE questions SET qualification='FSc Part 1' WHERE id=?",(qid,));self.c.commit()
        scope,args=sm._programme_scope_sql(sm._programme_aliases('FSc Part 1'))
        self.assertEqual(self.c.execute(f'SELECT COUNT(*) FROM questions q WHERE {scope}',args).fetchone()[0],0)
    def test_legacy_qualification_fallback_only_when_programme_blank(self):
        qid=self.scoped_question();self.c.execute("UPDATE questions SET programme='' WHERE id=?",(qid,));self.c.commit()
        scope,args=sm._programme_scope_sql(sm._programme_aliases('FSc Part 1'))
        self.assertEqual(self.c.execute(f'SELECT COUNT(*) FROM questions q WHERE {scope}',args).fetchone()[0],1)
    def test_local_session_rejects_cross_programme_before_write(self):
        qid=self.scoped_question('MDCAT');before=self.snapshot('assessment_sessions')
        with self.assertRaisesRegex(Exception,'ASSESSMENT_PROGRAMME_MISMATCH'):self.start([qid])
        self.assertEqual(self.snapshot('assessment_sessions'),before)
    def test_new_answer_evidence_is_frozen_at_submission(self):
        qid,aid,attempt=self.answer_one()
        row=self.c.execute('SELECT evidence_context_json FROM attempt_answers WHERE attempt_id=?',(attempt['id'],)).fetchone()
        context=json.loads(row[0]);self.assertEqual(context['programme'],'FSc Part 1');self.assertEqual(context['subject'],'Physics')
        self.c.execute("UPDATE questions SET subject='Chemistry',chapter='Elsewhere',programme='MDCAT',question_version=2 WHERE id=?",(qid,));self.c.commit()
        evidence=sm.learner_answer_evidence(self.c,self.uid,'FSc Part 1','Physics','Measurements')
        self.assertEqual(len(evidence),1);self.assertEqual(evidence[0]['context_authority'],'FROZEN_CONTEXT')
        self.assertEqual(sm.learner_answer_evidence(self.c,self.uid,'MDCAT'),[])
    def test_corrupt_frozen_context_never_falls_back_to_current_question(self):
        _,_,attempt=self.answer_one()
        self.c.execute('UPDATE attempt_answers SET evidence_context_json=? WHERE attempt_id=?',('{"schema":"forged"}',attempt['id']));self.c.commit()
        self.assertEqual(sm.learner_answer_evidence(self.c,self.uid),[])
    def test_fsc_evidence_does_not_appear_in_mdcat_all_main_getters(self):
        self.answer_one();self.answer_one(correct=False)
        self.switch('MDCAT')
        self.assertEqual(sm._student_accuracy(self.c,self.uid),(0,0))
        self.assertEqual(sm.eligible_attempts(self.c,self.uid),[])
        self.assertEqual(sm._tested_chapters(self.c,self.uid),set())
        self.assertEqual(ux._subject_snapshot(self.c,self.uid,'Physics')['answered'],0)
        self.assertEqual(sm.student_analytics(self.c,self.uid)['tests_completed'],0)
        self.switch('FSc Part 1')
        self.assertEqual(sm._student_accuracy(self.c,self.uid),(2,50))
    def test_per_answer_ineligible_evidence_excluded(self):
        _,_,attempt=self.answer_one()
        self.c.execute("UPDATE attempt_answers SET marking_status='AUTO_UNSCORED',mastery_evidence_eligible=0,marks_awarded=NULL WHERE attempt_id=?",(attempt['id'],));self.c.commit()
        self.assertEqual(sm.learner_answer_evidence(self.c,self.uid),[])
    def test_attempt_ineligible_guided_demo_and_competition_excluded(self):
        _,_,attempt=self.answer_one()
        for col,value in [('marking_status','AUTO_UNSCORED'),('mastery_evidence_eligible',0),('guided_mode',1),('assessment_kind','demo_progress'),('assessment_kind','science_genius')]:
            with self.subTest(col=col,value=value):
                before=attempt[col];self.c.execute(f'UPDATE attempts SET {col}=? WHERE id=?',(value,attempt['id']));self.c.commit()
                self.assertEqual(sm.learner_answer_evidence(self.c,self.uid),[]);self.assertEqual(sm.eligible_attempts(self.c,self.uid),[])
                self.c.execute(f'UPDATE attempts SET {col}=? WHERE id=?',(before,attempt['id']));self.c.commit()
    def test_unscoped_legacy_attempt_not_reattributed_on_switch(self):
        _,_,attempt=self.answer_one()
        self.c.execute("UPDATE attempts SET programme='' WHERE id=?",(attempt['id'],));self.c.commit()
        for programme in ('FSc Part 1','FSc Part 2','MDCAT'):
            self.switch(programme);self.assertEqual(sm.learner_answer_evidence(self.c,self.uid),[])
    def test_learning_and_recall_states_partition_identical_lo(self):
        self.answer_one('FSc Part 1',False);self.answer_one('MDCAT',True)
        states=self.snapshot('student_learning_states')
        self.assertEqual(len(states),2)
        self.assertEqual({r['programme'] for r in states},{'FSc Part 1','MDCAT'})
        self.assertEqual(len({r['area_key'] for r in states}),2)
        self.c.execute("UPDATE recall_items SET next_due_date='2000-01-01'");self.c.commit()
        self.switch('MDCAT')
        self.assertTrue(all(r['programme']=='MDCAT' for r in sm.due_recall_items(self.c,self.uid)))
        self.assertFalse(any(r.get('programme')=='FSc Part 1' for r in sm.student_weak_areas(self.c,self.uid)))
    def test_unscoped_old_learning_cache_not_shown_under_new_programme(self):
        self.c.execute("INSERT INTO student_learning_states(student_id,area_key,subject,area_name,status,evidence_count,accuracy) VALUES(?,'LEGACY','Physics','Legacy','Confirmed Weak Area',10,10)",(self.uid,));self.c.commit()
        self.switch('MDCAT');self.assertEqual(sm.student_weak_areas(self.c,self.uid),[])
    def test_no_cross_programme_mastery_record_fallback(self):
        self.master_record('FSc Part 1',level='Distinction')
        self.switch('MDCAT');data=sm.chapter_mastery_opportunity(self.c,self.uid,'Physics','Measurements','MDCAT')
        self.assertNotEqual(data.get('existing_level'),'Distinction')
    def test_plan_selected_by_explicit_target_not_latest_other_programme(self):
        # Missing programme is not a licence to reuse some other exam's starting coverage.
        self.answer_one()
        self.assertEqual(sm._tested_chapters(self.c,self.uid,'MDCAT'),set())
        self.assertEqual(sm._tested_chapters(self.c,self.uid,'FSc Part 1'),{('Physics','Measurements')})
    def test_fixed_student_boot_preserves_owner_modified_state(self):
        with patch.dict(os.environ,{'SCOREMAX_STAGING_TEST_STUDENT_PASSWORD':'Synthetic-First-Only!'}):ux._ensure_fixed_test_student()
        self.c.execute("UPDATE users SET account_status='disabled',active_programme='MDCAT',session_version=8,password_hash='synthetic-owner-changed' WHERE username=?",(ux.TEST_STUDENT_USERNAME,));self.c.commit()
        before=self.snapshot('users')
        with patch.dict(os.environ,{'SCOREMAX_STAGING_TEST_STUDENT_PASSWORD':'Synthetic-Second-Only!'}):ux._ensure_fixed_test_student()
        self.assertEqual(self.snapshot('users'),before)
    def test_zero_slider_is_real_zero_and_50_neutral(self):
        base=dict(sm.mastery_policy(self.c,'Exam Ready'))
        baseline=sm.effective_mastery_requirements(base,{'mastery_standard_score':50})
        self.assertEqual(baseline['min_accuracy'],base['min_accuracy'])
        for score in (0,50,100):
            result=sm.effective_mastery_requirements(base,{'mastery_standard_score':score})
            self.assertEqual(result['mastery_standard_score'],score)
        low=sm.effective_mastery_requirements(base,{'mastery_standard_score':0})
        high=sm.effective_mastery_requirements(base,{'mastery_standard_score':100})
        self.assertLess(low['min_accuracy'],baseline['min_accuracy']);self.assertGreater(high['min_accuracy'],baseline['min_accuracy'])
    def test_explicit_zero_baseline_shares_preserved(self):
        base=dict(sm.mastery_policy(self.c,'Exam Ready'));base.update(min_accuracy=0,target_band_pct=0,unseen_family_pct=0,min_breadth_pct=0)
        req=sm.effective_mastery_requirements(base,{'mastery_standard_score':50})
        for key in ('min_accuracy','target_band_pct','unseen_family_pct','min_breadth_pct'):self.assertEqual(req[key],0)
    def test_policy_score_invalid_values_rejected(self):
        for v in (float('nan'),float('inf'),-1,101,50.5,True,'not a number'):
            with self.subTest(v=str(v)),self.assertRaises(ValueError):sm.policy_score(v)
    def test_invalid_scopes_cannot_become_global(self):
        for kind,key in [('anything',''),('global','FSc Part 1'),('programme',''),('subject','FSc Part 1|'),('chapter','Physics|Measurements'),('blueprint','0')]:
            with self.subTest(kind=kind,key=key),self.assertRaises(ValueError):sm.normalise_policy_scope(kind,key)
    def test_programme_policy_only_marks_matching_records_due(self):
        first=self.master_record('FSc Part 1');second=self.master_record('MDCAT')
        before=self.snapshot('attempts');pid=self.policy('programme','FSc Part 1');self.assertEqual(self.activate(pid).status_code,302)
        self.assertEqual(self.status(first),'Verification Due');self.assertEqual(self.status(second),'Verified')
        self.assertEqual(self.snapshot('attempts'),before);self.assertEqual(len(self.snapshot('mastery_history')),1)
        self.assertEqual(self.c.execute('SELECT mastery_level FROM mastery_records WHERE id=?',(first,)).fetchone()[0],'Exam Ready')
    def test_composite_subject_scope_does_not_hit_other_exam_or_subject(self):
        records=[self.master_record(p,s) for p,s in [('FSc Part 1','Physics'),('FSc Part 1','Chemistry'),('MDCAT','Physics')]]
        self.activate(self.policy('subject','FSc Part 1|Physics'))
        self.assertEqual([self.status(x) for x in records],['Verification Due','Verified','Verified'])
    def test_composite_chapter_scope_is_exact(self):
        records=[self.master_record('FSc Part 1','Physics',ch) for ch in ['Measurements','Other']]
        self.activate(self.policy('chapter','FSc Part 1|Physics|Measurements'))
        self.assertEqual([self.status(x) for x in records],['Verification Due','Verified'])
    def test_bare_subject_scope_intentionally_matches_all_programmes(self):
        records=[self.master_record(p) for p in ['FSc Part 1','MDCAT']]
        self.activate(self.policy('subject','Physics'))
        self.assertEqual([self.status(x) for x in records],['Verification Due','Verification Due'])
    def test_more_specific_policy_protects_against_unrelated_global_tightening(self):
        protected=self.master_record('FSc Part 1');other=self.master_record('MDCAT')
        self.policy('programme','FSc Part 1',standard=50,status='ACTIVE')
        self.activate(self.policy('global','',standard=100))
        self.assertEqual(self.status(protected),'Verified');self.assertEqual(self.status(other),'Verification Due')
    def test_scope_activation_compares_effective_precedence_not_only_previous_same_scope(self):
        record=self.master_record()
        self.c.execute("UPDATE assessment_assembly_policies SET mastery_standard_score=100 WHERE status='ACTIVE'");self.c.commit()
        self.activate(self.policy('programme','FSc Part 1',standard=60))
        self.assertEqual(self.status(record),'Verified')
    def test_tightening_after_lower_global_flags_new_programme_policy(self):
        record=self.master_record()
        self.c.execute("UPDATE assessment_assembly_policies SET mastery_standard_score=0 WHERE status='ACTIVE'");self.c.commit()
        self.activate(self.policy('programme','FSc Part 1',standard=50))
        self.assertEqual(self.status(record),'Verification Due')
    def test_repeat_activation_has_no_repeated_history_or_mutation(self):
        self.master_record();pid=self.policy();self.activate(pid)
        before={t:self.snapshot(t) for t in ['mastery_records','mastery_history','assessment_assembly_policies']}
        self.activate(pid)
        self.assertEqual({t:self.snapshot(t) for t in before},before)
    def test_activation_requires_reason_and_admin_csrf(self):
        record=self.master_record();pid=self.policy();before=self.snapshot('assessment_assembly_policies')
        self.activate(pid,'')
        self.assertEqual(self.snapshot('assessment_assembly_policies'),before);self.assertEqual(self.status(record),'Verified')
        self.assertEqual(self.client_for('admin').post(f'/admin/assessment-policies/{pid}/activate',data={'reason':'X'},base_url='https://localhost').status_code,400)
        r=self.client.post(f'/admin/assessment-policies/{pid}/activate',data={'reason':'X','_csrf_token':'synthetic-csrf'},base_url='https://localhost')
        self.assertIn(r.status_code,(302,403));self.assertEqual(self.snapshot('assessment_assembly_policies'),before)
    def test_create_global_zero_sliders_has_real_historical_preview(self):
        self.form_history()
        r=self.client_for('admin').post('/admin/assessment-policies',data={'_csrf_token':'synthetic-csrf','scope_type':'global','scope_key':'','policy_version':'SYN-ZERO','rigor_score':'0','mastery_standard_score':'0','reason':'Synthetic zero'},base_url='https://localhost')
        self.assertEqual(r.status_code,302)
        p=self.c.execute("SELECT * FROM assessment_assembly_policies WHERE policy_version='SYN-ZERO'").fetchone()
        self.assertIsNotNone(p);self.assertEqual(p['mastery_standard_score'],0);self.assertEqual(p['rigor_score'],0)
        self.assertEqual(json.loads(p['preview_json'])['historical_simulation']['observed_forms'],1)
    def test_create_malformed_policy_has_no_database_mutation(self):
        before=self.snapshot('assessment_assembly_policies')
        for extra in [{'scope_type':'bad'},{'mastery_standard_score':'nan'},{'rigor_score':'101'},{'scope_type':'programme','scope_key':''}]:
            r=self.client_for('admin').post('/admin/assessment-policies',data={'_csrf_token':'synthetic-csrf','scope_type':'global','policy_version':'BAD','reason':'Synthetic',**extra},base_url='https://localhost')
            self.assertEqual(r.status_code,302);self.assertEqual(self.snapshot('assessment_assembly_policies'),before)
    def test_historical_preview_scope_and_unknown_denominator(self):
        self.form_history('FSc Part 1',True);self.form_history('FSc Part 1',False);self.form_history('MDCAT',True)
        preview=sm.simulate_policy_impact(self.c,None,80,'programme','FSc Part 1')
        self.assertEqual(preview['observed_forms'],2);self.assertEqual(preview['assessable_forms'],1);self.assertEqual(preview['unassessable_forms'],1)
        self.assertEqual(len(preview['levels']),1);self.assertIsNotNone(preview['levels'][0]['estimated_proposed_form_pass_rate'])
    def test_historical_preview_all_incomplete_reports_unknown_not_zero(self):
        self.form_history(complete=False)
        preview=sm.simulate_policy_impact(self.c,None,100,'global','')
        self.assertIsNone(preview['levels'][0]['estimated_proposed_form_pass_rate'])
        self.assertEqual(preview['assessable_forms'],0)
    def test_level_form_rejects_nonfinite_and_out_of_bounds_before_write(self):
        base=dict(sm.mastery_policy(self.c,'Exam Ready'));before=self.snapshot('mastery_policies')
        fields={k:str(base[k] if base[k] is not None else '') for k in ('min_forms','min_questions','min_accuracy','verification_days','external_percentile_target','target_band_pct','unseen_family_pct','min_breadth_pct')}
        for field,bad in [('min_accuracy','nan'),('target_band_pct','inf'),('min_breadth_pct','-1'),('min_questions','3.5'),('min_forms','0')]:
            data={'_csrf_token':'synthetic-csrf','mastery_level':'Exam Ready','reason':'Synthetic',**fields,field:bad}
            self.assertEqual(self.client_for('admin').post('/admin/mastery-rigor/level',data=data,base_url='https://localhost').status_code,302)
            self.assertEqual(self.snapshot('mastery_policies'),before)
    def test_owner_zero_breadth_setting_survives_schema_initializer(self):
        self.c.execute("UPDATE mastery_policies SET min_breadth_pct=0 WHERE mastery_level='Exam Ready'");self.c.commit()
        admin_runtime.ensure_mastery_rigor_schema(sm)
        self.assertEqual(sm.mastery_policy(self.c,'Exam Ready')['min_breadth_pct'],0)
    def test_missing_curriculum_register_never_uses_question_count(self):
        for _ in range(20):self.scoped_question()
        with self.assertRaisesRegex(ValueError,'coverage register'):sm.mastery_coverage_contract(self.c,'FSc Part 1','Physics','Measurements')
    def test_fixed_coverage_denominator_independent_of_inventory_growth_and_retirement(self):
        cfg=self.coverage(n=4);before=sm.mastery_coverage_contract(self.c,'FSc Part 1','Physics','Measurements')
        self.scoped_question(nodes=[cfg['required_node_ids'][0]])
        for _ in range(20):self.scoped_question(nodes=['UNRELATED'])
        self.c.execute('UPDATE questions SET active=0');self.c.commit()
        after=sm.mastery_coverage_contract(self.c,'FSc Part 1','Physics','Measurements')
        self.assertEqual(before,after);self.assertEqual(len(after['required_node_ids']),4)
    def test_family_or_question_ids_do_not_count_as_curriculum_coverage(self):
        self.assertEqual(sm.question_coverage_nodes({'family_id':'FAKE','question_id':'FAKE','learning_outcome':'FAKE','topic':'FAKE'}),set())
    def test_governed_coverage_source_and_node_status_required(self):
        cfg=self.coverage();self.c.execute("UPDATE universal_knowledge_nodes SET status='CANDIDATE' WHERE knowledge_node_id=?",(cfg['required_node_ids'][0],));self.c.commit()
        with self.assertRaises(ValueError):sm.mastery_coverage_contract(self.c,'FSc Part 1','Physics','Measurements')
    def test_curriculum_source_hash_mismatch_is_blocked(self):
        cfg=self.coverage();self.c.execute('UPDATE universal_source_documents SET file_hash=? WHERE source_id=?',('b'*64,cfg['source_id']));self.c.commit()
        with self.assertRaises(ValueError):sm.mastery_coverage_contract(self.c,'FSc Part 1','Physics','Measurements')
    def test_conflicting_active_curriculum_registers_are_blocked(self):
        cfg=self.coverage();cfg=copy.deepcopy(cfg);cfg['mandatory_node_ids']=[cfg['required_node_ids'][0]]
        self.policy('programme','FSc Part 1',status='ACTIVE',evidence={'curriculum_coverage_contracts':[cfg]})
        with self.assertRaisesRegex(ValueError,'unique'):sm.mastery_coverage_contract(self.c,'FSc Part 1','Physics','Measurements')
    def test_mastery_form_meets_fixed_node_target_and_novelty_quotas(self):
        self.configure_small_mastery();cfg=self.coverage(n=4,mandatory=[3]);self.create_mastery_bank(cfg)
        chosen,meta=sm.build_mastery_form(self.c,self.uid,'chapter','Exam Ready','FSc Part 1','Physics','Measurements')
        self.assertEqual(len(chosen),5);self.assertGreaterEqual(meta['mastery_breadth_ratio'],.75);self.assertTrue(meta['mastery_mandatory_covered'])
        self.assertEqual(len(meta['mastery_coverage_snapshot']['required_node_ids']),4)
        self.assertEqual(meta['mastery_effective_policy']['coverage_contract_checksum'],meta['mastery_coverage_snapshot']['checksum_sha256'])
    def test_mastery_form_missing_mandatory_node_fails_even_with_many_questions(self):
        self.configure_small_mastery();cfg=self.coverage(n=4,mandatory=[3])
        for _ in range(15):self.scoped_question(nodes=[cfg['required_node_ids'][0]])
        with self.assertRaises(ValueError):sm.build_mastery_form(self.c,self.uid,'chapter','Exam Ready','FSc Part 1','Physics','Measurements')
    def test_mastery_counting_cross_level_previous_exposures_not_forgotten(self):
        key=sm.mastery_scope_key('chapter','FSc Part 1','Physics','Measurements')
        for i in range(8):
            self.c.execute("INSERT INTO mastery_form_results(student_id,scope_type,scope_key,target_level,family_ids_json) VALUES(?,'chapter',?,'Foundation',?)",(self.uid,key,json.dumps([f'F{i}'])))
        self.c.commit();self.assertEqual(sm._mastery_previous_families(self.c,self.uid,'chapter',key,'Exam Ready'),{f'F{i}' for i in range(8)})
    def test_mastery_result_promotes_only_under_matching_current_contract(self):
        self.configure_small_mastery();cfg=self.coverage(n=4,mandatory=[0]);self.create_mastery_bank(cfg)
        chosen,meta,aid=self.new_mastery_session()
        self.assertEqual(self.submit(aid).status_code,302)
        attempt=self.attempt(aid);self.assertEqual(attempt['score'],100)
        results=self.snapshot('mastery_form_results');self.assertEqual(len(results),1);self.assertEqual(results[0]['passed'],1)
        self.assertEqual(len(self.snapshot('mastery_records')),1)
        self.assertEqual(self.snapshot('mastery_records')[0]['mastery_level'],'Exam Ready')
    def test_inflight_older_policy_keeps_mark_without_new_standard_promotion(self):
        self.configure_small_mastery();cfg=self.coverage(n=4);self.create_mastery_bank(cfg)
        _,meta,aid=self.new_mastery_session()
        self.activate(self.policy('programme','FSc Part 1',standard=100))
        self.assertEqual(self.submit(aid).status_code,302)
        self.assertEqual(self.attempt(aid)['score'],100)
        self.assertEqual(len(self.snapshot('mastery_records')),0)
        result=self.snapshot('mastery_form_results')[0]
        self.assertEqual(json.loads(result['effective_policy_json'])['assembly_policy_id'],meta['assembly_policy_id'])
    def test_no_form_promotion_with_corrupted_frozen_coverage(self):
        self.configure_small_mastery();cfg=self.coverage();self.create_mastery_bank(cfg)
        _,meta,aid=self.new_mastery_session()
        meta['mastery_coverage_snapshot']['required_node_ids'].append('FORGED')
        self.c.execute('UPDATE assessment_sessions SET meta_json=? WHERE id=?',(json.dumps(meta),aid));self.c.commit()
        self.assertEqual(self.submit(aid).status_code,302)
        self.assertEqual(self.attempt(aid)['score'],100)
        self.assertEqual(len(self.snapshot('mastery_records')),0)
    def test_data_integrity_after_native_submit_and_scoped_policy_change(self):
        self.answer_one();self.master_record();self.activate(self.policy('programme','FSc Part 1'))
        self.assertEqual(self.c.execute('PRAGMA integrity_check').fetchone()[0],'ok')
        self.assertEqual(self.c.execute('PRAGMA foreign_key_check').fetchall(),[])

    def test_main_dashboard_uses_selected_programme_evidence(self):
        self.answer_one('FSc Part 1');self.switch('MDCAT')
        data=sm.student_dashboard_intelligence(self.c,self.uid)
        self.assertEqual(data['subjects'],[]);self.assertEqual(data['chapters'],[])
        self.assertEqual(data['weekly']['answered'],0);self.assertEqual(data['improvements'],[])
    def test_high_practice_accuracy_does_not_fabricate_formal_mastery_badge(self):
        self.answer_one()
        data=sm.student_dashboard_intelligence(self.c,self.uid)
        self.assertEqual(data['subjects'][0]['accuracy'],100)
        self.assertEqual(data['subjects'][0]['mastery'],'Not verified')
    def test_old_mastery_admin_bookmark_redirects_to_single_editor(self):
        r=self.client_for('admin').get('/admin/mastery-rules',base_url='https://localhost')
        self.assertEqual(r.status_code,302);self.assertTrue(r.location.endswith('/admin/mastery-rigor'))
    def test_old_mastery_rule_post_cannot_bypass_validation_or_reason(self):
        before=self.snapshot('mastery_policies')
        r=self.client_for('admin').post('/admin/mastery-rules',data={'_csrf_token':'synthetic-csrf','mastery_level':'Exam Ready','min_accuracy':'nan'},base_url='https://localhost')
        self.assertEqual(r.status_code,302);self.assertEqual(self.snapshot('mastery_policies'),before)
    def test_current_mastery_list_does_not_expire_unselected_programme(self):
        old=self.master_record('FSc Part 1');selected=self.master_record('MDCAT')
        self.c.execute("UPDATE mastery_records SET verification_due_at='2000-01-01' WHERE id=?",(old,));self.c.commit()
        self.switch('MDCAT');records=sm.current_mastery_records(self.c,self.uid)
        self.assertEqual([r['id'] for r in records],[selected]);self.assertEqual(self.status(old),'Verified')
    def test_global_draft_copies_frozen_curriculum_register_not_question_inventory(self):
        cfg=self.coverage()
        r=self.client_for('admin').post('/admin/assessment-policies',data={'_csrf_token':'synthetic-csrf','scope_type':'global','policy_version':'SYN-COPY','reason':'Synthetic','rigor_score':'50','mastery_standard_score':'55'},base_url='https://localhost')
        self.assertEqual(r.status_code,302)
        row=self.c.execute("SELECT * FROM assessment_assembly_policies WHERE policy_version='SYN-COPY'").fetchone()
        self.assertEqual(json.loads(row['evidence_config_json'])['curriculum_coverage_contracts'],[cfg])
    def test_practice_exposure_already_counts_as_seen_in_form_assembly(self):
        qid,_,_=self.answer_one()
        family=self.c.execute('SELECT family_id FROM questions WHERE id=?',(qid,)).fetchone()[0]
        seen=sm._mastery_previous_families(self.c,self.uid,'chapter','FSc Part 1|Physics|Measurements','Distinction')
        self.assertIn(family,seen)
    def test_zero_slider_ui_selection_mix_is_less_demanding_than_baseline(self):
        self.assertGreater(sm.rigor_mix(0)['Easy'],sm.rigor_mix(50)['Easy'])
        self.assertLess(sm.rigor_mix(0)['Difficult'],sm.rigor_mix(50)['Difficult'])
    def test_fixed_student_identity_collision_is_not_reassigned(self):
        self.c.execute('UPDATE users SET email=? WHERE id=?',(ux.TEST_STUDENT_EMAIL,self.uid));self.c.commit()
        before=self.snapshot('users')
        with patch.dict(os.environ,{'SCOREMAX_STAGING_TEST_STUDENT_PASSWORD':'Synthetic-Only!'}),self.assertRaises(RuntimeError):ux._ensure_fixed_test_student()
        self.assertEqual(self.snapshot('users'),before)

    def test_detailed_level_tightening_only_marks_that_level_due(self):
        first=self.master_record('FSc Part 1',level='Exam Ready');other=self.master_record('MDCAT',level='Distinction')
        base=dict(sm.mastery_policy(self.c,'Exam Ready'))
        fields={k:str(base[k] if base[k] is not None else '') for k in ('min_forms','min_questions','min_accuracy','verification_days','external_percentile_target','target_band_pct','unseen_family_pct','min_breadth_pct')}
        fields['min_accuracy']='95'
        before=self.snapshot('attempts')
        r=self.client_for('admin').post('/admin/mastery-rigor/level',data={'_csrf_token':'synthetic-csrf','mastery_level':'Exam Ready','reason':'Synthetic tightening',**fields},base_url='https://localhost')
        self.assertEqual(r.status_code,302)
        self.assertEqual(self.status(first),'Verification Due');self.assertEqual(self.status(other),'Verified')
        self.assertEqual(self.snapshot('attempts'),before)
        self.assertEqual(len(self.snapshot('mastery_policy_change_audit_v1')),1)
    def test_programme_switch_respects_interest_gate_and_preserves_current_selection(self):
        before=self.programme()
        response=self.client.post('/student/programme',data={'_csrf_token':'synthetic-csrf','programme_code':'mdcat','return_to':'/student/learn-vnext'},base_url='https://localhost')
        # Discover the existing route rather than infer a wrong public URL.
        if response.status_code==404:
            with sm.app.test_request_context():path=sm.url_for('student_programme_switch')
            response=self.client.post(path,data={'_csrf_token':'synthetic-csrf','programme_code':'mdcat','return_to':'/student/learn-vnext'},base_url='https://localhost')
        self.assertEqual(response.status_code,302);self.assertEqual(self.programme(),before)
        self.assertIn('interest',response.location)

    def test_populated_student_pages_preserve_context_and_do_not_error(self):
        self.answer_one()
        with sm.app.test_request_context():
            paths=[sm.url_for(name) for name in ('student_dashboard','ux_student_learn','student_analytics_page','mastery_page','weak_areas_page','study_plan_page')]
        for programme in ('FSc Part 1','FSc Part 2','MDCAT'):
            self.switch(programme)
            for path in paths:
                with self.subTest(programme=programme,path=path):
                    response=self.client.get(path,base_url='https://localhost',follow_redirects=True)
                    self.assertLess(response.status_code,500)
                    self.assertEqual(self.programme(),programme)
    def test_same_lo_exam_scores_stay_separate_in_both_directions(self):
        self.answer_one('FSc Part 1',True);self.answer_one('MDCAT',False)
        for programme,expected in [('FSc Part 1',100),('MDCAT',0)]:
            self.switch(programme)
            stats=ux._subject_snapshot(self.c,self.uid,'Physics')
            self.assertEqual(stats['answered'],1);self.assertEqual(stats['avg_accuracy'],expected)
        self.switch('FSc Part 2');self.assertEqual(ux._subject_snapshot(self.c,self.uid,'Physics')['answered'],0)
    def test_invalid_coverage_evidence_shape_is_controlled_error(self):
        for value in ('[]','{"curriculum_coverage_contracts":{}}'):
            self.c.execute("UPDATE assessment_assembly_policies SET evidence_config_json=? WHERE status='ACTIVE'",(value,));self.c.commit()
            with self.assertRaises(ValueError):sm.mastery_coverage_contract(self.c,'FSc Part 1','Physics','Measurements')
    def test_invalid_mandatory_node_value_is_controlled_error(self):
        cfg=self.coverage();cfg['mandatory_node_ids']=[{}]
        self.c.execute("UPDATE assessment_assembly_policies SET evidence_config_json=? WHERE status='ACTIVE'",(json.dumps({'curriculum_coverage_contracts':[cfg]}),));self.c.commit()
        with self.assertRaises(ValueError):sm.mastery_coverage_contract(self.c,'FSc Part 1','Physics','Measurements')
    def test_blank_source_hash_is_not_approved_coverage(self):
        cfg=self.coverage();cfg['source_checksum_sha256']=''
        self.c.execute("UPDATE assessment_assembly_policies SET evidence_config_json=? WHERE status='ACTIVE'",(json.dumps({'curriculum_coverage_contracts':[cfg]}),))
        self.c.execute("UPDATE universal_source_documents SET file_hash='' WHERE source_id=?",(cfg['source_id'],));self.c.commit()
        with self.assertRaises(ValueError):sm.mastery_coverage_contract(self.c,'FSc Part 1','Physics','Measurements')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--report',default='programme_mastery_repair_results.json');args=parser.parse_args()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ProgrammeMasteryRepair))
    report={'suite':'PROGRAMME_MASTERY_REPAIR_V3','tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'passed':result.wasSuccessful(),
      'failure_names':[str(t) for t,_ in result.failures+result.errors],'source_hashes':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['app.py','ux_student_batch.py','ux_catalogue_browser.py','ux_mastery_rigor_admin.py']},
      'production_modified':False,'deployment_triggered':False,'full_mastery_model_frozen':False,'actual_curriculum_delivery_qualified':False,
      'scope':'Synthetic native programme, eligible evidence, scoped policy and fixed coverage invariants. Not full platform or actual Cross50 qualification.'}
    Path(args.report).write_text(json.dumps(report,indent=2)+'\n');print('PROGRAMME_MASTERY_REPAIR_RESULT='+json.dumps(report,sort_keys=True))
    raise SystemExit(0 if result.wasSuccessful() else 1)
