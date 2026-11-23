"""Signed image identity, bounded decoding and immutable pin display."""
from pathlib import Path
import base64,copy,hashlib,importlib.util,json,sqlite3,tempfile,unittest
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('native_media_test',ROOT/'scoremax_runtime_v669b/ph_learner_media_v1.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=')
def stimulus():
 d={'stimulus_id':'opaque::image/A-0001','stimulus_version_id':'opaque::image-version/001','stimulus_type':'IMAGE_REFERENCE','content':{'uri':'data:image/png;base64,'+base64.b64encode(PNG).decode(),'file_sha256':hashlib.sha256(PNG).hexdigest(),'mime_type':'image/png'},'provenance':{'software_fixture_only':True}}
 d['stimulus_checksum_sha256']=m.digest(d);return d
class NativeLearnerMedia(unittest.TestCase):
 def test_exact_signed_bytes_and_small_reference_are_preserved(self):
  s=stimulus();before=copy.deepcopy(s);ref=m.image_ref(s);self.assertEqual(ref['media_sha256'],hashlib.sha256(PNG).hexdigest());self.assertNotIn('uri',ref);self.assertEqual(s,before)
 def test_plain_question_does_not_open_database_or_change_projection(self):
  p={'answer_config':'{}'};self.assertIs(m.project(p,{'content':{}},{}),p)
  def forbidden():raise AssertionError('Unexpected DB query')
  self.assertIsNone(m.learner_uri({'answer_config':'{}'},forbidden))
 def test_http_svg_javascript_and_unknown_data_types_are_rejected(self):
  for uri in ['https://example.invalid/a.png','javascript:alert(1)','data:image/svg+xml;base64,PHN2Zy8+','file:///private.png','data:text/html;base64,PGh0bWw+']:
   s=stimulus();s['content']['uri']=uri
   with self.assertRaises(ValueError):m.image_content(s)
 def test_forged_hash_mime_corrupt_image_and_oversize_fail(self):
  for data in [{'file_sha256':'0'*64},{'mime_type':'image/jpeg'},{'uri':'data:image/png;base64,AAAA','file_sha256':hashlib.sha256(b'\0\0\0').hexdigest()},{'uri':'data:image/png;base64,'+'A'*(m.MAX_BYTES*4//3+10)}]:
   s=stimulus();s['content'].update(data)
   with self.assertRaises(ValueError):m.image_content(s)
 def test_changed_stimulus_without_new_checksum_is_rejected(self):
  s=stimulus();s['provenance']['unexpected']='changed'
  with self.assertRaisesRegex(ValueError,'CHECKSUM'):m.image_ref(s)
 def test_source_reference_is_opaque_and_cannot_bind_another_question(self):
  s=stimulus();ref=m.image_ref(s)
  with self.assertRaisesRegex(ValueError,'BINDING'):m.validated_ref(ref,{'stimulus_ref':'1'})
  for key,value in [('version','APPROVED'),('media_sha256',''),('stimulus_id',True),('mime_type','image/svg+xml')]:
   with self.assertRaises(ValueError):m.validated_ref(ref|{key:value})
 def test_effective_projection_keeps_only_validated_version_reference(self):
  s=stimulus();q={'content':{'stimulus_ref':s['stimulus_id']}};base={'answer_config':'{}','marks':2};out=m.project(base,q,{s['stimulus_id']:s});restored=m.preserve_ref(out,{'answer_config':'{}'},q['content']);self.assertEqual(json.loads(out['answer_config']),json.loads(restored['answer_config']));self.assertEqual(base['answer_config'],'{}')
 def test_existing_version_store_supplies_the_exact_pinned_image(self):
  with tempfile.TemporaryDirectory() as directory:
   p=Path(directory)/'software.db';c=sqlite3.connect(p);c.execute('CREATE TABLE integration_ph_stimulus_version_store(stimulus_id TEXT,stimulus_version_id TEXT,stimulus_checksum_sha256 TEXT,immutable_payload_json TEXT)');s=stimulus();c.execute('INSERT INTO integration_ph_stimulus_version_store VALUES(?,?,?,?)',(s['stimulus_id'],s['stimulus_version_id'],s['stimulus_checksum_sha256'],m.canonical(s)));c.commit();c.close()
   def connect():
    r=sqlite3.connect(p);r.row_factory=sqlite3.Row;return r
   q={'answer_config':m.canonical({m.KEY:m.image_ref(s)})};self.assertEqual(m.learner_uri(q,connect),s['content']['uri'])
   bad=copy.deepcopy(s);bad['content']['uri']='https://example.invalid/changed';c=sqlite3.connect(p);c.execute('UPDATE integration_ph_stimulus_version_store SET immutable_payload_json=?',(m.canonical(bad),));c.commit();c.close()
   with self.assertRaises(ValueError):m.learner_uri(q,connect)
if __name__=='__main__':unittest.main()
