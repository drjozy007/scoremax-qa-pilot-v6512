"""Synthetic portability/regression tests; no academic or release authority."""
import copy, unittest
import qualify_native_adaptive_chemistry as previous
import native_scoring_operations_v1 as ops
import ux_constructed_auto_marker as marker

def synthetic(terms=True):
    evidence=['Alpha forces.','Beta forces.'] if terms else ['X = 2 m3.']
    row={'Question_ID':'SYNTHETIC-NOT-ACADEMIC','Learner_Question':'Name synthetic categories.' if terms else 'State synthetic quantity X.',
      'Model_Answer':' '.join(evidence),'Canonical_Accepted_Evidence':' | '.join(evidence),
      'Required_Produced_Representation':'NONE','Numerical_Tolerance_Rule':'NOT_APPLICABLE','Significant_Figures_Rule':'NOT_APPLICABLE',
      'Scoring_Mode':'POINT_BASED_RUBRIC','Auto_Marking_Eligibility':'HUMAN_REVIEW_REQUIRED',
      'SAQ_Demand_Archetype':'ARCH-NAME' if terms else 'ARCH-IDENTIFY','Mark_Point_Count':len(evidence),
      'Mark_Point_Values':';'.join('1' for x in evidence),'Marks':len(evidence),'Acceptable_Alternatives':'NONE',
      'Partial_Credit_Rule':'Award 1 mark for each independently satisfied mark point.',
      'Contradiction_Rule':'A direct contradiction of a credited proposition removes credit for that proposition; unrelated extra information is ignored.',
      'Order_Sensitivity':'YES only where a ranking/order is explicitly demanded; otherwise equivalent sentence order is accepted.'}
    rubric={'version':'PH-SAQ-SCORING-CONTRACT-1','maximum_marks':len(evidence),'required_mark_points':[
      {'id':f'p{i}','marks':1,'description':e,'accepted_expressions':[e]} for i,e in enumerate(evidence,1)]}
    rubric['contract_sha256']=ops.stable_hash(rubric)
    bound=ops.attach_native_operations(rubric,row)
    return row,bound,marker.compile_contract({},row['Model_Answer'],row['Marks'],row['Learner_Question'],marking_cfg={'rubric':bound})

class OperationPrimitives(unittest.TestCase):
    def test_term_points_partial_duplicate_contradiction_and_unknown(self):
        row,b,c=synthetic()
        cases=[('Beta forces, Alpha forces',2),('Alpha forces and Beta forces',2),('Alpha forces',1),
               ('Alpha forces; Alpha forces',1),('Alpha forces; Beta forces; not Alpha forces',1),
               ('Alpha forces; not Alpha forces',0),('Alpha forces are wrong; Beta forces',None),
               ('Alpha forces? Beta forces.',None),('Unknown forces',None),('',0)]
        for response,expected in cases:
            r=marker.mark(c,response);self.assertEqual(r['marks_awarded'],expected);self.assertEqual(r['evidence_eligible'],expected is not None)
        self.assertEqual(ops.attach_native_operations(b,row),b)
        self.assertEqual(b['native_scoring']['source_row']['Auto_Marking_Eligibility'],'HUMAN_REVIEW_REQUIRED')

    def test_quantity_sign_units_and_unknown(self):
        row,b,c=synthetic(False)
        for response,expected in [('2 m^3',1),('2.0 m³',1),('-2 m3',0),('4 m3',0),('2 m2',None),
                                  ('2',None),('2 m3; -2 m3',0),('X=2 m3; X=2 m3',1),('2 m3; unknown',None)]:
            self.assertEqual(marker.mark(c,response)['marks_awarded'],expected)

    def test_point_or_source_tampering_and_representation_fail_closed(self):
        row,b,c=synthetic();changed=copy.deepcopy(b);changed['required_mark_points'][0]['marks']=2
        changed.pop('contract_sha256');changed['contract_sha256']=ops.stable_hash(changed)
        self.assertIsNone(ops.compile_native_rubric(changed,2,row['Learner_Question'],row['Model_Answer']))
        row['Required_Produced_Representation']='DRAWING';self.assertIsNone(ops.derive_controlled_operations(row))
        row['Required_Produced_Representation']='NONE';row['Learner_Question']='Rank synthetic categories.'
        self.assertIsNone(ops.derive_controlled_operations(row))

if __name__=='__main__':unittest.main()
