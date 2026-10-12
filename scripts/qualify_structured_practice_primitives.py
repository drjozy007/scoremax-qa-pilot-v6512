"""Synthetic portability tests. No academic inventory or release authority."""
import copy,json,shutil,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
TMP=tempfile.TemporaryDirectory(prefix='structured-practice-portable-')
for name in ('ux_constructed_auto_marker.py','native_scoring_operations_v1.py','native_structured_practice.py'):
    shutil.copy2(ROOT/'ux_vnext_overlay'/name,Path(TMP.name)/name)
(Path(TMP.name)/'written_response_engine.py').write_text('import re\n'+(ROOT/'ux_vnext_overlay/assessment_written_response_v2.py').read_text(encoding='utf-8'),encoding='utf-8')
sys.path.insert(0,TMP.name)
import native_scoring_operations_v1 as native
import native_structured_practice as structured
import ux_constructed_auto_marker as marker


def fixture(evidence):
    row={'Learner_Question':'[SYNTHETIC] Supply the evidence.','Model_Answer':' '.join(evidence),
      'Required_Produced_Representation':'NONE','Numerical_Tolerance_Rule':'NOT_APPLICABLE',
      'Significant_Figures_Rule':'NOT_APPLICABLE','Canonical_Accepted_Evidence':' | '.join(evidence),
      'Partial_Credit_Rule':'Award 1 mark for each independently satisfied mark point.',
      'Contradiction_Rule':'A direct contradiction of a credited proposition removes credit for that proposition; unrelated extra information is ignored.',
      'Equation_Equivalence_Rule':'Algebraically equivalent rearrangements are accepted when they preserve the same relationship.',
      'Mark_Point_Count':len(evidence),'Mark_Point_Values':';'.join('1' for _ in evidence),'Marks':len(evidence)}
    rubric={'version':'PH-SAQ-SCORING-CONTRACT-1','maximum_marks':len(evidence),
      'required_mark_points':[{'id':f'p{i}','marks':1,'description':e,'accepted_expressions':[e]} for i,e in enumerate(evidence,1)]}
    rubric['contract_sha256']=native.stable_hash(rubric)
    bound=structured.attach(rubric,row)
    compiled=marker.compile_contract({},row['Model_Answer'],row['Marks'],row['Learner_Question'],marking_cfg={'rubric':bound})
    return row,bound,compiled


def response(assertions=(),equations=()):
    return json.dumps({'version':structured.RESPONSE_VERSION,'assertions':[dict(zip(('subject','relation','object'),a)) for a in assertions],
                       'equations':list(equations),'values':[]})


class Primitives(unittest.TestCase):
    def test_practice_partial_duplicate_negation_and_unknown(self):
        _,_,contract=fixture(['A sample has no fixed boundary.','A sample occupies available space.'])
        a=('sample','has','no fixed boundary');b=('sample','occupies','available space')
        for answer,expected in [(response([a,b]),2),(response([a,a]),1),(response([a,b,('sample','has','fixed boundary')]),1),
                                (response([('available space','occupies','sample')]),None),('',0),('[]',None)]:
            result=marker.mark(contract,answer);self.assertEqual(result['marks_awarded'],expected);self.assertFalse(result['evidence_eligible'])

    def test_equation_and_working_allocation(self):
        _,_,contract=fixture(['X = YZ.','Rearranging gives Y = X/Z.'])
        for equations,expected in [(['X=YZ','Y=X/Z'],2),(['X=YZ','X=YZ'],1),(['X=-YZ'],None),(['X=Y'],None),(['X=YZ','X=Y'],None)]:
            self.assertEqual(marker.mark(contract,response(equations=equations))['marks_awarded'],expected)

    def test_unrecognised_source_is_not_executable(self):
        for clause in ['It is larger because these are warmer.','A sample is cold unless it is heated.','A sample may or may not expand.']:
            self.assertIsNone(structured.parse_bundle(clause))

    def test_source_marks_and_policy_cannot_be_changed(self):
        row,bound,contract=fixture(['A sample occupies available space.'])
        for change in ('marks','authority','evidence'):
            altered=copy.deepcopy(bound)
            if change=='marks':altered['required_mark_points'][0]['marks']=2
            if change=='authority':altered['native_scoring']['practice_authority']['exam_readiness_evidence']=True
            if change=='evidence':altered['native_scoring']['operations'][0]['assertions'][0]['object']='invented space'
            altered.pop('contract_sha256');altered['contract_sha256']=native.stable_hash(altered)
            self.assertIsNone(native.compile_native_rubric(altered,1,row['Learner_Question'],row['Model_Answer']))

    def test_response_duplicate_keys_and_injection_abstain(self):
        _,_,contract=fixture(['A sample occupies available space.'])
        for answer in ['{"version":"PH-STRUCTURED-PRACTICE-1","version":"other","assertions":[],"equations":[],"values":[]}',
                       response(equations=['__import__("os").system("false")']),response([('sample','occupies','available space')]*51)]:
            self.assertIsNone(marker.mark(contract,answer)['marks_awarded'])

if __name__=='__main__':unittest.main()
