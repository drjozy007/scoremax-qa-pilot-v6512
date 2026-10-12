"""Focused PR174 receiver regression; existing marker is imported unchanged."""
import copy
import json
import unittest

from qualify_existing_ph_compatibility import ExistingPHCompatibility, integration


class PR174AdmissionBoundary(ExistingPHCompatibility):
    # Reuse fixture helpers, not the previous full assessment qualification suite.
    def constructed(self, family='SHORT_RESPONSE', rubric=None):
        e=self.envelope()
        q=e['payload']['questions'][0]
        q['content'].update(question_family_type=family, options=[],
                            response_contract='CONSTRUCTED_RESPONSE',
                            exam_question_type='SAQ', stem='State the approved relation.')
        q['content']['marking'].update(key_type='RUBRIC_ONLY' if rubric else 'TEXT',
            key=None if rubric else 'A governed model answer is not a scoring contract.',
            marks=1, negative_marks=0, numeric_tolerance=None, accepted_answers=[],
            scoring_contract='RUBRIC_REVIEW', rubric=rubric)
        return self.rehash(e)

    def assert_empty_staging(self):
        for table in ('integration_ph_content_releases','integration_ph_question_version_store',
                      'integration_ph_release_question_membership','integration_ph_product_activation_authorizations'):
            self.assertEqual(self.c.execute('SELECT COUNT(*) FROM '+table).fetchone()[0],0,table)

    def test_pr174_unsupported_family_durable_rejection_before_writes(self):
        e=self.constructed('UNSUPPORTED_PR174_FAMILY')
        r=self.admit(e,422)
        self.assertEqual(r['status'],'REJECTED')
        self.assertTrue(any('UNKNOWN_QUESTION_FAMILY' in x['message'] for x in r['errors']))
        self.assertIn(e['payload']['questions'][0]['question_version_id'],r['errors'][-1]['message'])
        self.assertEqual(self.admit(e,422)['receipt_id'],r['receipt_id'])
        self.assert_empty_staging()
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM integration_receipts').fetchone()[0],1)

    def test_pr174_symbolic_drawing_not_silently_retyped_as_prose(self):
        e=self.constructed('SYMBOLIC_CONSTRUCTED_RESPONSE')
        r=self.admit(e,422)
        self.assertTrue(any('UNKNOWN_QUESTION_FAMILY' in x['message'] for x in r['errors']))
        self.assert_empty_staging()

    def test_pr174_conceptual_text_never_becomes_fill_blank(self):
        e=self.constructed()
        self.admit(e,422)
        self.assert_empty_staging()

    def test_pr174_approved_rubric_reaches_existing_marker(self):
        rubric={'version':'PH-SAQ-SCORING-CONTRACT-1','maximum_marks':1,
          'auto_marking_eligibility':'DETERMINISTICALLY_SCORABLE','scoring_type':'EXACT_BOUNDED',
          'required_mark_points':[{'id':'P1','marks':1,'description':'Approved relation',
            'accepted_expressions':['PV = nRT'],'accepted_synonyms':[],'contradictions':[]}]}
        e=self.constructed('SHORT_RESPONSE',rubric)
        r=self.admit(e)
        v=self.qversion(e);projection=json.loads(v['scoremax_projection_json'])
        self.assertEqual(r['status'],'ACCEPTED')
        self.assertEqual(json.loads(v['content_json']),e['payload']['questions'][0]['content'])
        self.assertEqual(json.loads(projection['marking_config'])['rubric'],rubric)
        self.assertEqual(projection['ph_is_auto_markable'],1)
        from ux_constructed_auto_marker import mark
        contract=integration.question_contracts.validate_assessment_contract(projection)['constructed_contract']
        self.assertEqual(mark(contract,'PV = nRT')['marks_awarded'],1)
        self.assertEqual(self.c.execute('SELECT local_status FROM integration_ph_content_releases').fetchone()[0],'STAGED')
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM integration_ph_product_activation_authorizations').fetchone()[0],0)

    def test_pr174_changed_rejected_identity_quarantined(self):
        e=self.constructed();first=self.admit(e,422)
        e['payload']['questions'][0]['content']['stem']='A changed immutable payload.'
        self.rehash(e)
        second=self.admit(e,409)
        self.assertEqual(second['status'],'QUARANTINED')
        self.assertNotEqual(first['payload_checksum_sha256'],second['payload_checksum_sha256'])
        self.assert_empty_staging()


if __name__=='__main__':
    suite=unittest.TestSuite(PR174AdmissionBoundary(n) for n in dir(PR174AdmissionBoundary) if n.startswith('test_pr174_'))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())
