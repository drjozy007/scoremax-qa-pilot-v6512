"""Small structural regressions for the existing authored-clause tokenizer."""
import importlib.util
from pathlib import Path
import re
import sys
import unittest

path = Path(sys.argv.pop(1)) if len(sys.argv)>1 and sys.argv[1].endswith('.py') else Path(__file__).resolve().parents[1]/'ux_vnext_overlay/assessment_written_response_v2.py'
ns = {'re':re}
exec(compile(path.read_text(),str(path),'exec'),ns)

def rubric(positive, negative=(), sensitive=True):
    return {'version':'SM-RUBRIC-CLAUSES-1','maximum_marks':len(positive),
            'case_sensitive':sensitive,
            'required_mark_points':[{'id':str(i),'description':x,'marks':1,'accepted_phrases':[x]}
                                    for i,x in enumerate(positive)],
            'contradictions':[{'phrase':x,'point_ids':[str(i)]} for x,i in negative]}

def score(r, answer):
    return ns['mark_written_response'](r,answer)['proposed_mark']

class DelimiterCompatibility(unittest.TestCase):
    def test_literal_decimal_and_internal_semicolon(self):
        r=rubric(['R = 0.0821 atm dm3 K^-1 mol^-1.','State one; then state two.'])
        self.assertEqual(score(r,'R = 0.0821 atm dm3 K^-1 mol^-1. State one; then state two.'),2)

    def test_decimal_cannot_be_reinterpreted_as_two_points(self):
        self.assertIsNone(score(rubric(['0','0821']),'0.0821'))

    def test_whole_known_clause_has_existing_priority(self):
        r=rubric(['First; second.','First','second'])
        self.assertEqual(score(r,'First; second.'),1)

    def test_unknown_prefix_suffix_and_negation_fail_closed(self):
        r=rubric(['Correct assertion.'])
        for answer in ['Not Correct assertion.','Correct assertion. Wrong.','Wrong. Correct assertion.','Correct assertion?']:
            self.assertIsNone(score(r,answer))

    def test_contradiction_and_duplicate_credit(self):
        r=rubric(['Correct assertion.'],[('Opposite assertion.',0)])
        self.assertEqual(score(r,'Correct assertion.\nCorrect assertion.'),1)
        for answer in ['Correct assertion. Opposite assertion.','Opposite assertion. Correct assertion.']:
            self.assertEqual(score(r,answer),0)

    def test_ambiguous_attribution_fails_closed(self):
        r=rubric(['First; second.','First','second','Third'])
        self.assertIsNone(score(r,'First; second. Third.'))

    def test_case_policy_is_not_broadened(self):
        self.assertIsNone(score(rubric(['CO','Next']),'Co. Next.'))
        self.assertEqual(score(rubric(['Correct assertion','Next'],sensitive=False),'CORRECT ASSERTION. NEXT.'),2)
        self.assertIsNone(score(rubric(['i','next'],sensitive=False),'ı. next.'))

    def test_long_repetition_is_bounded_without_overcredit(self):
        self.assertEqual(score(rubric(['A']),'A.'*4500),1)

if __name__=='__main__':unittest.main(verbosity=2)
