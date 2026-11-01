"""Targeted source-derived contract, response, renderer and rollback safeguards.

No application startup, production database, academic QA, learner session or network.
"""
import ast
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT/'scoremax_runtime_v669b'
sys.path.insert(0,str(RUNTIME))
sys.path.insert(0,str(ROOT/'ux_vnext_overlay/biology_receiver_20261027'))
import ph_practice_contracts as contracts
import question_contract_engine as engine
import scoremax_integration_v1 as receiver
from shared_practice_publisher import bind_practice_material
from werkzeug.datastructures import MultiDict
from jinja2 import Environment, FileSystemLoader, select_autoescape

CASES=json.loads(Path(os.environ.get('PH_PRACTICE_SOURCE_CASES',str(Path(__file__).with_name('shared_practice_source_cases.json')))).read_text())


def projected(case):
    source=case['source']
    content={'question_family_type':source['Question_Type'] if case['kind']=='CLOZE' else 'SHORT_RESPONSE',
             'stem':source['Learner_Question'],'marking':{'marks':1,'key_type':'TEXT','key':''},'options':[]}
    context={'display':{'practice_mode':'GUIDED_SELF_ASSESSMENT','practice_approval_reference':'OWNER_SOURCE_DERIVED_UNIT_CHECK'}} if case['kind']=='SAQ' else {}
    material=bind_practice_material({'content':content},{},context,source,case['workbook_sha256'])
    q={'content':material['content'],'curriculum':{'programme_id':'FSC_PART_I','grade_year_id':'11'}}
    return receiver._projection(q,{})


def marker():
    tree=ast.parse((RUNTIME/'app.py').read_text())
    names={'canonical_question_type','safe_json','_mark_objective_response','mark_question_result'}
    functions=[x for x in tree.body if isinstance(x,ast.FunctionDef) and x.name in names]
    assert {x.name for x in functions}==names
    env={'json':json,'question_contracts':engine}
    exec(compile(ast.Module(body=functions,type_ignores=[]),'<native-marking-functions>','exec'),env)
    return env['mark_question_result']


class SharedPractice(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.mark=staticmethod(marker())

    def test_exact_source_single_gap_reuses_fill_blank_and_explicit_alternative(self):
        for case in CASES:
            if case['kind']!='CLOZE' or case['source']['Gap_Count']!=1:continue
            q=projected(case);self.assertEqual(engine.runtime_type_from_row(q),'fill_blank')
            ac=json.loads(q['answer_config'])
            for answer in ac['accepted_answers']:
                self.assertTrue(self.mark(q,' '+answer.swapcase()+' ')['is_correct'])
            self.assertFalse(self.mark(q,'unsupported source answer')['is_correct'])

    def test_every_source_multigap_preserves_gap_identity_and_answers(self):
        for case in CASES:
            if case['kind']!='CLOZE' or case['source']['Gap_Count']==1:continue
            q=projected(case);c=engine.validate_assessment_contract(q)['cloze_contract']
            self.assertEqual(len(c['gaps']),case['source']['Gap_Count'])
            mapping={g['id']:g['accepted_answers'][-1] for g in c['gaps']}
            form=MultiDict([('gap::'+key,value) for key,value in mapping.items()])
            answer=engine.canonical_submission('multi_gap_cloze',form)
            self.assertEqual(json.loads(answer),mapping)
            result=self.mark(q,answer)
            self.assertTrue(result['is_correct']);self.assertEqual(result['marks_awarded'],case['source']['Total_Practice_Score'])
            values=list(mapping.values());swapped=dict(zip(mapping,values[1:]+values[:1]))
            if swapped!=mapping:self.assertFalse(self.mark(q,json.dumps(swapped))['is_correct'])
            self.assertFalse(self.mark(q,'')['is_correct'])

    def test_no_collapse_missing_extra_duplicate_or_cross_gap_response(self):
        case=next(c for c in CASES if c['kind']=='CLOZE' and c['source']['Gap_Count']==2)
        q=projected(case);gap=json.loads(q['answer_config'])['cloze_contract']['gaps'][0]
        with self.assertRaisesRegex(engine.QuestionContractError,'SINGLE_FIELD'):
            engine.canonical_submission('multi_gap_cloze',MultiDict([('answer','a,b')]))
        with self.assertRaisesRegex(engine.QuestionContractError,'DUPLICATE_GAP'):
            engine.canonical_submission('multi_gap_cloze',MultiDict([('gap::'+gap['id'],'a'),('gap::'+gap['id'],'b')]))
        for answer in ({gap['id']:'a'},{'unknown':'a'},['a','b']):
            with self.assertRaises(engine.QuestionContractError):self.mark(q,json.dumps(answer))

    def test_multigap_rendering_has_one_safe_saved_input_per_gap_and_no_keys(self):
        env=Environment(loader=FileSystemLoader(RUNTIME/'templates'),autoescape=select_autoescape())
        env.globals['url_for']=lambda *a,**k:'/existing-question-report'
        template=env.get_template('_learner_question_surface.html')
        for case in CASES:
            if case['kind']!='CLOZE' or case['source']['Gap_Count']==1:continue
            q=projected(case);q.update(id=1,level='Foundation')
            ac=json.loads(q['answer_config']);mc=json.loads(q['marking_config']);gaps=ac['cloze_contract']['gaps']
            html=template.render(q=q,qtype='multi_gap_cloze',answer_cfg=ac,marking_cfg=mc,
                  answers={},saved_struct={gaps[0]['id']:'<saved>'},options=[],request=type('Request',(),{'path':'/existing'})())
            self.assertEqual(html.count('name="gap::'),len(gaps))
            self.assertIn('&lt;saved&gt;',html)
            self.assertNotIn('name="answer"',html)
            self.assertNotIn('canonical_answer',html);self.assertNotIn('accepted_answers',html)

    def test_guided_source_rubrics_remain_unscored_without_ai_or_mark_authority(self):
        for case in CASES:
            if case['kind']!='SAQ':continue
            q=projected(case);decision=receiver._ph_validate_scored_or_guided_assessment(q)
            self.assertFalse(decision['scoring_authorised']);self.assertEqual(q['ph_is_auto_markable'],0)
            guided=engine.validate_assessment_contract(q)['guided_contract']
            self.assertTrue(all(v is False for v in guided['authority'].values()))
            with self.assertRaisesRegex(engine.QuestionContractError,'GUIDED_PRACTICE_HAS_NO_MARKS'):
                self.mark(q,case['source']['Model_Answer'])
            bad=deepcopy(q);bad['ph_is_auto_markable']=1
            with self.assertRaisesRegex(engine.QuestionContractError,'AUTHORITY_CONFLICT'):
                receiver._ph_validate_scored_or_guided_assessment(bad)

    def test_guided_preserves_distinct_rubric_instructions_and_accepted_evidence(self):
        case=deepcopy(next(c for c in CASES if c['kind']=='SAQ'))
        source=case['source'];old=source['Marking_Rubric']
        source['Marking_Rubric']=old.replace('1. 1 mark — ','1. 1 mark — Describe this source criterion: ',1)
        q=projected(case)
        import guided_self_assessment
        view=guided_self_assessment.guidance(q)
        self.assertIn(source['Marking_Rubric'],view['source_guidance'])
        points=json.loads(q['marking_config'])['rubric']['required_mark_points']
        self.assertTrue(points[0]['source_rubric_criterion'].startswith('Describe this source criterion: '))
        self.assertNotEqual(points[0]['description'],points[0]['source_rubric_criterion'])
        with self.assertRaisesRegex(engine.QuestionContractError,'GUIDED_PRACTICE_HAS_NO_MARKS'):
            self.mark(q,source['Model_Answer'])
        source['Marking_Rubric']=source['Marking_Rubric'].replace('1. 1 mark —','1. 99 marks —',1)
        with self.assertRaisesRegex(ValueError,'RUBRIC_CONFLICT'):projected(case)

    def test_bad_source_or_contract_is_held_independently(self):
        original=next(c for c in CASES if c['kind']=='CLOZE')
        for field,value in [('Canonical_Answers','G99=invented'),('Gap_Count',2),('Auto_Marking_Eligibility','UNKNOWN'),('Learner_Question','Different source stem')]:
            bad=deepcopy(original);bad['source'][field]=value
            with self.assertRaises((ValueError,engine.QuestionContractError)):projected(bad)
            self.assertEqual(engine.runtime_type_from_row(projected(original)),'fill_blank')
        bad=deepcopy(next(c for c in CASES if c['kind']=='SAQ'));bad['source']['Mark_Point_Values']='99|99'
        with self.assertRaises(ValueError):projected(bad)

    def test_contract_checksum_stem_and_marks_bindings(self):
        q=projected(next(c for c in CASES if c['kind']=='CLOZE' and c['source']['Gap_Count']==2))
        for key,value in [('question','changed question'),('marks',99)]:
            bad=deepcopy(q);bad[key]=value
            with self.assertRaises(engine.QuestionContractError):engine.validate_assessment_contract(bad)
        ac=json.loads(q['answer_config']);ac['cloze_contract']['gaps'][0]['accepted_answers'].append('invented')
        q['answer_config']=json.dumps(ac)
        with self.assertRaisesRegex(engine.QuestionContractError,'CHECKSUM'):engine.validate_assessment_contract(q)

    def test_real_source_practice_contracts_pass_only_the_precise_rubric_semantic_boundary(self):
        for case in CASES:
            source=case['source'];family=source['Question_Type'] if case['kind']=='CLOZE' else 'SHORT_RESPONSE'
            context={'display':{'practice_mode':'GUIDED_SELF_ASSESSMENT','practice_approval_reference':'SOURCE_UNIT_CHECK'}} if case['kind']=='SAQ' else {}
            material=bind_practice_material({'content':{'question_family_type':family,'stem':source['Learner_Question'],
                    'options':[],'marking':{'marks':1,'key_type':'TEXT','key':'','numeric_tolerance':None}}},{},context,source,case['workbook_sha256'])
            q={'question_id':source['Question_ID'],'question_version_id':'unit-version','content':material['content']}
            self.assertEqual(receiver._ph_semantic_errors_with_governed_guided([q],[],'1.2.0'),[])
            bad=deepcopy(q);bad['content']['marking']['negative_marks']=1
            self.assertIn('INVALID_NEGATIVE_MARKS',[x['code'] for x in receiver._ph_semantic_errors_with_governed_guided([bad],[],'1.2.0')])
            bad=deepcopy(q)
            rubric=bad['content']['marking']['rubric']
            if case['kind']=='CLOZE':rubric['cloze_gap_contract']['gaps'][0]['canonical_answer']='invented'
            else:rubric['guided_self_assessment']['authority']['ai_marking']=True
            self.assertIn('MARKING_MODE_INCOHERENT',[x['code'] for x in receiver._ph_semantic_errors_with_governed_guided([bad],[],'1.2.0')])

    def test_scoped_native_claim_leaves_unrelated_and_terminal_rows_untouched(self):
        c=sqlite3.connect(':memory:');c.row_factory=sqlite3.Row
        c.execute('CREATE TABLE integration_outbox(id INTEGER PRIMARY KEY,contract_name TEXT,status TEXT,next_attempt_at TEXT,created_at TEXT,claim_token TEXT,claim_expires_at TEXT)')
        c.executemany('INSERT INTO integration_outbox VALUES(?,?,?,?,?,?,?)',[(1,'SM_GE_PRODUCT_EVENT_V1','PENDING','','2020','',''),(2,'SM_PH_CONTENT_DELIVERY_ACK_V1','PENDING','','2021','',''),(3,'SM_PH_CONTENT_DELIVERY_ACK_V1','DELIVERED','','2019','','')]);c.commit()
        before=tuple(c.execute('SELECT * FROM integration_outbox WHERE id=1').fetchone())
        claimed=receiver._claim_due(c,limit=1,outbox_ids=[2,3])
        self.assertEqual([r['id'] for r in claimed],[2]);self.assertEqual(tuple(c.execute('SELECT * FROM integration_outbox WHERE id=1').fetchone()),before)
        self.assertEqual(c.execute('SELECT status FROM integration_outbox WHERE id=3').fetchone()[0],'DELIVERED')
        for scope in ([],[True],[2,2],[-1]):
            with self.assertRaises(ValueError):receiver._claim_due(c,outbox_ids=scope)
        c.close()

    def test_existing_mcq_true_false_and_fill_blank_keep_native_marking(self):
        for family,key_type,key,options in [
            ('MCQ_SINGLE','SINGLE_OPTION','A',[{'option_id':'A','text':'Accepted'},{'option_id':'B','text':'Other'}]),
            ('TRUE_FALSE','BOOLEAN','TRUE',[{'option_id':'TRUE','text':'True'},{'option_id':'FALSE','text':'False'}]),
            ('CLOZE','TEXT','Eukarya',[])]:
            content={'question_family_type':family,'stem':'Existing accepted practice item',
                     'options':options,'marking':{'key_type':key_type,'key':key,'marks':1,'negative_marks':0,'accepted_answers':[key]}}
            q=receiver._projection({'content':content},{})
            self.assertTrue(self.mark(q,key)['is_correct'])
            self.assertEqual(self.mark(q,key)['marks_awarded'],1)
            self.assertFalse(self.mark(q,'wrong')['is_correct'])

    def test_accepted_release_activation_signing_and_immutable_store_guards_unchanged(self):
        expected=json.loads(Path(__file__).with_name('shared_practice_rollback_pins.json').read_text())
        for path,pins in expected.items():
            source=(RUNTIME/path).read_text();tree=ast.parse(source)
            for name,sha in pins.items():
                bodies=[ast.get_source_segment(source,x) for x in tree.body if isinstance(x,ast.FunctionDef) and x.name==name]
                self.assertTrue(bodies,name)
                self.assertEqual(hashlib.sha256(json.dumps(bodies,separators=(',',':')).encode()).hexdigest(),sha,(path,name))


if __name__=='__main__':unittest.main()
