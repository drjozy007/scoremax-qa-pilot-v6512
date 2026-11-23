"""Scored-SAQ software fixtures; none confers approval on real source questions."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import unittest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO/'scoremax_runtime_v669b'))
import scored_saq_runtime_v1 as boundary
import question_contract_engine as contracts
from ux_constructed_auto_marker import mark


def fixture_row(any_n=False, semantic=False):
    points = [{'id':'opaque/p::'+str(i), 'description':phrase, 'marks':1,
               'accepted_expressions':[phrase], 'accepted_synonyms':[],
               'contradictions':['not '+phrase]} for i,phrase in enumerate(
                   ['Criterion alpha is satisfied', 'Criterion beta is satisfied'] +
                   (['Criterion gamma is satisfied'] if any_n else []))]
    rubric = {'version':'PH-SAQ-SCORING-CONTRACT-1','maximum_marks':2,
              'auto_marking_eligibility':'RUBRIC_SEMANTICALLY_SCORABLE' if semantic else 'DETERMINISTICALLY_SCORABLE',
              'scoring_type':'ANY_N_FROM_VALID_SET' if any_n else 'EXACT_BOUNDED',
              'required_mark_points':points,'source_marking_evidence_sha256':'2'*64}
    if any_n:rubric['required_count']=2
    rubric['contract_sha256']=boundary.digest(rubric)
    q = {'question_id':'fixture-native','ph_question_id':'opaque/Q::α',
         'ph_question_version_id':'version::β','ph_question_checksum_sha256':'9'*64,
         'qtype':'Constructed Response','question':'State two approved fixture criteria.',
         'answer':'Criterion alpha is satisfied. Criterion beta is satisfied.', 'marks':2,
         'answer_config':'{}','ph_evidence_role':'INDEPENDENT','ph_independent_mastery_weight':1,
         'ph_dependency_type':'NONE','ph_mastery_ceiling':'EXAM_READY',
         'ph_market_id':'PK','ph_programme_id':'FSc Part 1','ph_subject_id':'Fixture',
         'ph_chapter_id':'opaque/chapter::x'}
    academic={'policy':'PH-NATIVE-INDEPENDENT-SAQ-APPROVAL-1','native_question_id':17,
              'material_checksum_sha256':'1'*64,'basis':'CURRENT_NATIVE_HUMAN_REVIEW_WITH_EXACT_RUBRIC',
              'native_review_snapshot_checksum_sha256':'8'*64,
              'attribution':[{'assignment_item_public_id':'software-fixture-only',
                  'readiness_state':'R1_CLEARED','canonical_snapshot_checksum':'8'*64,
                  'response_public_id':'software-response-only','reviewer_id':1,'response_status':'SUBMITTED'}],
              'new_academic_approval_conferred':False}
    academic['decision_sha256']=boundary.digest(academic)
    e={'version':boundary.ELIGIBILITY,'question_id':q['ph_question_id'],'native_question_id':17,
       'source_question_id':'opaque::source/001','maximum_marks':2,
       'material_checksum_sha256':'1'*64,'source_row_sha256':'2'*64,
       'source_workbook_sha256':'3'*64,'truth_source_sha256':'4'*64,
       'source_snapshot_sha256':'5'*64,'source_academic_evidence_sha256':'6'*64,
       'rubric_contract_sha256':rubric['contract_sha256'],
       'learner_content_sha256':boundary.learner_content_hash(q['question'],q['answer'],q['marks'],rubric),
       'academic_approval':academic,
       'assessment_approval':{'basis':'SOURCE_AUTHORED_INDEPENDENT_ROLE_AND_CURRENT_NATIVE_REVIEW',
                              'source_evidence_sha256':'2'*64},
       'assessment_purpose':'INDEPENDENT_SCORED','independent_mastery_weight':1,
       'source_auto_marking_eligibility':'DETERMINISTICALLY_SCORABLE',
       'response_requirement':{'response_type':'TEXT','source_response_mode':'FREE_TEXT_CONSTRUCTED_RESPONSE',
                              'source_output_type':'PLAIN_TEXT','required_produced_representation':'NONE'},
       'destination':{**{k:q['ph_'+k] for k in ('market_id','programme_id','subject_id','chapter_id')},
                      'release_profile_id':'opaque::profile','release_profile_checksum_sha256':'7'*64},
       'mastery_scope':{'mastery_level':'FOUNDATION','assessment_ceiling':'EXAM_READY'},
       'response_requirement':{'response_type':'TEXT','source_response_mode':'FREE_TEXT_CONSTRUCTED_RESPONSE',
                               'source_output_type':'PLAIN_TEXT','required_produced_representation':'NONE'},
       'marking_requirement':{'allowed_routes':['DETERMINISTIC','QUALIFIED_AI'],
                              'official_ai_scoring_enabled':False}}
    e['contract_sha256']=boundary.digest(e)
    q['marking_config']=boundary.canonical({'marks':2,'auto_markable':True,
        'rubric':{'scoring_contract':rubric,'assessment_eligibility':e}})
    q['ph_provenance_snapshot_json']=boundary.canonical({'lineage':{'scored_assessment_contract':{
       'version':e['version'],'contract_sha256':e['contract_sha256'],
       'material_checksum_sha256':e['material_checksum_sha256'],
       'academic_approval_decision_sha256':academic['decision_sha256']}}})
    return q


def mutate_eligibility(q, fn):
    q=deepcopy(q); mc=json.loads(q['marking_config']); e=mc['rubric']['assessment_eligibility']
    fn(e); e.pop('contract_sha256',None); e['contract_sha256']=boundary.digest(e)
    q['marking_config']=boundary.canonical(mc)
    return q


class ScoredSAQTests(unittest.TestCase):
    def setUp(self): self.q=fixture_row()

    def test_marks_and_independent_weight_remain_distinct(self):
        result=contracts.validate_assessment_contract(self.q)
        self.assertEqual(result['maximum_marks'],2)
        self.assertEqual(result['assessment_eligibility']['independent_mastery_weight'],1)

    def test_full_partial_zero_and_unfamiliar_paraphrase(self):
        compiled=contracts.validate_assessment_contract(self.q)['constructed_contract']
        for response, expected in [('Criterion alpha is satisfied; Criterion beta is satisfied',2),
                                   ('Criterion beta is satisfied',1),
                                   ('not Criterion alpha is satisfied',0),('',0),
                                   ('Both fixture conditions hold in the required form',None)]:
            with self.subTest(response=response):
                out=mark(compiled,response)
                self.assertEqual(out['marks_awarded'],expected)
                self.assertEqual(out['evidence_eligible'],expected is not None)
                if expected is None:self.assertEqual(out['status'],'UNSCORED_PENDING_REVIEW')

    def test_any_two_caps_three_alternatives_and_repetition(self):
        q=fixture_row(any_n=True); compiled=contracts.validate_assessment_contract(q)['constructed_contract']
        self.assertEqual(mark(compiled,'Criterion alpha is satisfied; Criterion beta is satisfied; Criterion gamma is satisfied')['marks_awarded'],2)
        self.assertEqual(mark(compiled,'Criterion alpha is satisfied; Criterion alpha is satisfied')['marks_awarded'],1)

    def test_semantic_question_academically_eligible_but_not_scored_live(self):
        q=fixture_row(semantic=True); decision=boundary.capability(q)
        self.assertTrue(decision['academic_eligible']);self.assertTrue(decision['assessment_eligible'])
        self.assertFalse(decision['marking_qualified'])
        with self.assertRaisesRegex(ValueError,'CAPABILITY_PENDING'):contracts.validate_assessment_contract(q)

    def test_answer_or_stem_mutation_cannot_borrow_approval(self):
        for key in ('question','answer'):
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'LEARNER_CONTENT'):
                boundary.capability({**self.q,key:'Changed unapproved material'})

    def test_wrong_question_and_programme_fail(self):
        for key in ('ph_question_id','ph_programme_id'):
            with self.subTest(key=key),self.assertRaises(ValueError):
                boundary.capability({**self.q,key:'other'})

    def test_missing_immutable_version_or_checksum_fail(self):
        for key in ('ph_question_version_id','ph_question_checksum_sha256'):
            with self.subTest(key=key),self.assertRaises(ValueError):boundary.capability({**self.q,key:''})

    def test_weight_zero_boolean_and_dependent_never_formal(self):
        import ph_mastery_evidence
        for value in (0,False,True,float('nan')):
            self.assertFalse(ph_mastery_evidence.eligible_for_formal_mastery({**self.q,'ph_independent_mastery_weight':value}))
        self.assertFalse(ph_mastery_evidence.eligible_for_formal_mastery({**self.q,'ph_dependency_type':'SCAFFOLD'}))

    def test_wrong_marks_and_scope(self):
        with self.assertRaises(ValueError):boundary.capability({**self.q,'marks':3})
        for edit in [lambda e:e['academic_approval'].update(native_question_id=18),
                     lambda e:e['assessment_approval'].update(source_evidence_sha256='f'*64),
                     lambda e:e['mastery_scope'].update(mastery_level='DISTINCTION'),
                     lambda e:e['marking_requirement'].update(official_ai_scoring_enabled=True)]:
            with self.subTest(edit=edit),self.assertRaises(ValueError):boundary.capability(mutate_eligibility(self.q,edit))

    def test_provider_candidate_is_validated_but_stays_unscored(self):
        response='Criterion alpha is satisfied'
        rubric,_=boundary.parts(self.q['marking_config'])
        raw={'rubric_sha256':rubric['contract_sha256'],'response_sha256':hashlib.sha256(response.encode()).hexdigest(),
             'points':[{'id':p['id'],'awarded':1 if i==0 else 0,'evidence':response if i==0 else '',
                        'contradiction':False} for i,p in enumerate(rubric['required_mark_points'])], 'total_marks':1}
        out=boundary.qualify_provider_candidate(self.q,response,'opaque/answer-v1',lambda messages:raw)
        self.assertEqual(out['candidate_mark'],1);self.assertFalse(out['evidence_eligible'])
        self.assertFalse(out['official_ai_scoring_enabled']);self.assertIsNone(out['marks_awarded'])

    def test_provider_timeout_malformed_and_mark_invention_fail_unscored(self):
        for provider in [lambda _: (_ for _ in ()).throw(TimeoutError()), lambda _: {'total_marks':2},
                         lambda _: {'points':[{'id':'new invented point'}]}]:
            out=boundary.qualify_provider_candidate(self.q,'Criterion alpha is satisfied','v1',provider)
            self.assertIsNone(out['marks_awarded']);self.assertFalse(out['evidence_eligible'])

    def test_connecting_api_does_not_enable_official_scoring(self):
        called=[]
        out=boundary.optional_ai_mark(self.q,'answer',provider=lambda _:called.append(True))
        self.assertFalse(called);self.assertIsNone(out['marks_awarded']);self.assertFalse(out['evidence_eligible'])

    def resealed(self, mutate):
        q=deepcopy(self.q); mc=json.loads(q['marking_config']);e=mc['rubric']['assessment_eligibility']
        mutate(e)
        a=e['academic_approval'];a.pop('decision_sha256',None);a['decision_sha256']=boundary.digest(a)
        e.pop('contract_sha256',None);e['contract_sha256']=boundary.digest(e)
        q['marking_config']=boundary.canonical(mc)
        p=json.loads(q['ph_provenance_snapshot_json']);lineage=p['lineage']['scored_assessment_contract']
        lineage.update(contract_sha256=e['contract_sha256'],academic_approval_decision_sha256=a['decision_sha256'])
        q['ph_provenance_snapshot_json']=boundary.canonical(p)
        return q

    def test_whitespace_only_human_and_opaque_identities_fail(self):
        cases=[lambda e:e.update(question_id=' '),lambda e:e.update(source_question_id='  '),
               lambda e:e['academic_approval']['attribution'][0].update(response_public_id='  '),
               lambda e:e['academic_approval']['attribution'][0].update(assignment_item_public_id=' ')]
        for mutation in cases:
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                boundary.capability(self.resealed(mutation))

    def test_academic_native_id_remains_strict_integer(self):
        for invalid in (17.0,True,'17'):
            with self.subTest(invalid=invalid),self.assertRaises(ValueError):
                boundary.capability(self.resealed(lambda e:e['academic_approval'].update(native_question_id=invalid)))

    def test_semantic_assessor_labels_are_meaningful_and_canonically_distinct(self):
        for labels in [((' ',' '),('  ','  ')),(('Provider','Model'),(' provider ',' model '))]:
            def mutate(e):
                a=e['academic_approval'];a['basis']='CURRENT_NATIVE_INDEPENDENT_SEMANTIC_ASSESSMENTS'
                a['attribution']=[{'public_id':'fixture-review-'+str(i),'question_snapshot_checksum_sha256':'8'*64,
                    'provider_name':labels[i-1][0],'model_name':labels[i-1][1],'independent_slot':i,
                    'evidence_checksum_sha256':str(i)*64,'payload_sha256':str(i)*64} for i in (1,2)]
            with self.subTest(labels=labels),self.assertRaises(ValueError):boundary.capability(self.resealed(mutate))

    def test_whitespace_only_human_attribution_is_rejected(self):
        for key in ('assignment_item_public_id','response_public_id'):
            q=fixture_row();mc=json.loads(q['marking_config']);e=mc['rubric']['assessment_eligibility']
            a=e['academic_approval'];a['attribution'][0][key]='  \t '
            a['decision_sha256']=boundary.digest({k:v for k,v in a.items() if k!='decision_sha256'})
            e['contract_sha256']=boundary.digest({k:v for k,v in e.items() if k!='contract_sha256'})
            q['marking_config']=boundary.canonical(mc)
            lineage=json.loads(q['ph_provenance_snapshot_json'])
            lineage['lineage']['scored_assessment_contract'].update(contract_sha256=e['contract_sha256'],
                academic_approval_decision_sha256=a['decision_sha256'])
            q['ph_provenance_snapshot_json']=boundary.canonical(lineage)
            with self.subTest(key=key),self.assertRaisesRegex(ValueError,'HUMAN_REVIEW'):
                boundary.capability(q)


if __name__=='__main__': unittest.main()
