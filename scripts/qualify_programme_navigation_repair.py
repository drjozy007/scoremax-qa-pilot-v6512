"""Reuse the 67 programme/mastery regressions and add the native DOM authority regression.

No product bootstrap or remote service is added; all fixtures are isolated and synthetic.
"""
from __future__ import annotations
import argparse,hashlib,json,unittest
from pathlib import Path
from qualify_programme_mastery_repair import ProgrammeMasteryRepair,ROOT

class ProgrammeMasteryNavigationRepair(ProgrammeMasteryRepair):
    def test_cosmetic_overlay_preserves_native_programme_and_subject_controls(self):
        response=self.client.get('/student/learn-vnext',base_url='https://localhost')
        self.assertEqual(response.status_code,200)
        html=response.get_data(as_text=True)
        self.assertNotIn("stack.querySelectorAll('.programme-context-strip').forEach(x=>x.remove())",html)
        self.assertNotIn('.student-context-stack .programme-context-strip{display:none!important}',html)
        self.assertNotIn("strip.innerHTML='';subjects.forEach",html)
        self.assertIn("if(!strip.querySelector('a'))subjects.forEach",html)
        from qualify_assessment_contract_repair import Tags
        tags=Tags(html).tags
        for code in ('fsc1','fsc2','mdcat'):
            self.assertTrue(any(tag=='input' and attr.get('name')=='programme_code' and attr.get('value')==code for tag,attr in tags))
        self.assertTrue(any(tag=='form' and attr.get('action')=='/student/programme' and attr.get('method')=='post' for tag,attr in tags))
        self.assertEqual(self.programme(),'FSc Part 1')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--report',default='programme_mastery_navigation_results.json');args=parser.parse_args()
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ProgrammeMasteryNavigationRepair))
    report={'suite':'PROGRAMME_MASTERY_REPAIR_V3_BROWSER_CONTRACT','tests_run':result.testsRun,
      'failures':len(result.failures),'errors':len(result.errors),'passed':result.wasSuccessful(),
      'failure_names':[str(t) for t,_ in result.failures+result.errors],
      'source_hashes':{name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in
        ['app.py','ux_student_batch.py','ux_catalogue_browser.py','ux_mastery_rigor_admin.py','ux_staging_routes.py']},
      'production_modified':False,'deployment_triggered':False,'full_mastery_model_frozen':False,
      'actual_curriculum_delivery_qualified':False,
      'scope':'Original 67 programme/mastery tests plus preservation of native browser navigation. No real curriculum or bulk-import clearance.'}
    Path(args.report).write_text(json.dumps(report,indent=2)+'\n')
    print('PROGRAMME_MASTERY_REPAIR_RESULT='+json.dumps(report,sort_keys=True))
    raise SystemExit(0 if result.wasSuccessful() else 1)
