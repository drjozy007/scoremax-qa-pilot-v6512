"""Retained hosted measurements pass; missing side effects cannot be ignored."""
from pathlib import Path
import copy,json,base64,gzip,hashlib,importlib.util,unittest
P=Path(__file__).resolve().parent;s=importlib.util.spec_from_file_location('current_image_mixed_report',P/'qualify_source_image_mixed_report_v2.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def fixture():
 r=json.loads((P/'retained_hosted_image_mixed_fixture_v2.json').read_text());out=[]
 for n in ('mixed_native.json','mixed_native_mixed_actions.json'):
  p=r['reports'][n];raw=gzip.decompress(base64.b64decode(p['content']));assert hashlib.sha256(raw).hexdigest()==p['sha256'];out.append(json.loads(raw))
 return out
class CurrentImageReport(unittest.TestCase):
 def test_exact_retained_hosted_400_requests_nine_events_pass_without_new_measurement(self):
  r,a=fixture();out=m.qualify(r,a);self.assertEqual(out['status'],'PASSED');self.assertEqual(out['signed_POSTs'],6);self.assertEqual(out['authenticated_original_image_GETs'],3);self.assertLess(r['conditions'][0]['successful_nav_latency']['p95_ms'],1500)
 def test_every_signed_post_and_every_image_get_remains_mandatory(self):
  r,a=fixture()
  for i,x in enumerate(a['actions']):
   if 'path' not in x:continue
   bad=copy.deepcopy(a);bad['actions'].pop(i)
   with self.subTest(missing_event=i),self.assertRaises(ValueError):m.qualify(r,bad)
 def test_bad_latency_errors_missing_proof_scores_duplicates_and_image_drift_are_rejected(self):
  edits=[lambda r,a:r['conditions'][0]['successful_nav_latency'].update(p95_ms=1500),lambda r,a:r['conditions'][0].update(errors=1),lambda r,a:r['conditions'][0].update(level=1),lambda r,a:a.update(writer_errors=[{'message':'failed'}]),lambda r,a:a['actions'][-1]['native_writer_result'].update(pending_marks_awarded=0),lambda r,a:a['actions'][-1]['native_writer_result'].update(formal_mastery_rows_created=1),lambda r,a:a['actions'][-1]['native_writer_result'].update(native_attempts=2),lambda r,a:a['actions'][-1].update(preexisting_protected_tables_preserved=15),lambda r,a:a['actions'][2].update(exact_oversized_source_image_present=False),lambda r,a:a['actions'][2].update(path='/test/session/99999'),lambda r,a:a['actions'].append({'path':'/unknown','status':200})]
  for i,edit in enumerate(edits):
   r,a=fixture();edit(r,a)
   with self.subTest(drift=i),self.assertRaises(ValueError):m.qualify(r,a)
if __name__=='__main__':unittest.main()
