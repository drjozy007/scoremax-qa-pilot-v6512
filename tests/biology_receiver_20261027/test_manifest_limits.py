"""Manifest byte bounds; actual signed transport is exercised by the reused pull checks."""
import hashlib,io,json,os,sys,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'.test_deps'))
RUNTIME=Path(sys.argv.pop(1));sys.path.insert(0,str(RUNTIME))
import scoremax_integration_v1 as integration

class ManifestLimits(unittest.TestCase):
 def test_download_stops_at_existing_upload_limit_plus_one_byte(self):
  requests=[]
  class Response:
   def __enter__(self):return self
   def __exit__(self,*args):pass
   def read(self,count):requests.append(count);return b'x'*count
  class Opener:
   def open(self,*args,**kwargs):return Response()
  env={'SCOREMAX_MAX_UPLOAD_MB':'1','SCOREMAX_POWER_HOUSE_BASE_URL':'https://ph.example.invalid',
       'SCOREMAX_TO_POWER_HOUSE_TOKEN':'synthetic','SCOREMAX_TO_POWER_HOUSE_HMAC_SECRET':'synthetic'}
  with patch.dict(os.environ,env),patch.object(integration.urlrequest,'build_opener',return_value=Opener()):
   with self.assertRaisesRegex(ValueError,'exceeds configured upload byte limit'):
    integration._download_manifest_package('https://ph.example.invalid/api/package')
  self.assertEqual(requests,[1024*1024+1])
 def test_zip_expansion_is_rejected_before_crc_expansion(self):
  buffer=io.BytesIO()
  with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as archive:archive.writestr('oversize.json',b'x'*(2*1024*1024))
  data=buffer.getvalue()
  with patch.dict(os.environ,{'SCOREMAX_MAX_UPLOAD_MB':'1'}),patch.object(zipfile.ZipFile,'testzip',side_effect=AssertionError('Expanded before preflight')):
   with self.assertRaisesRegex(ValueError,'Expanded manifest package exceeds'):
    integration._load_manifest_package(data,{'package_checksum_sha256':hashlib.sha256(data).hexdigest()})
 def test_raw_archive_limit_is_checked_before_archive_processing(self):
  with patch.dict(os.environ,{'SCOREMAX_MAX_UPLOAD_MB':'1'}):
   with self.assertRaisesRegex(ValueError,'exceeds configured upload byte limit'):
    integration._load_manifest_package(b'x'*(1024*1024+1),{})
 def test_valid_existing_package_is_preserved_under_limit(self):
  original=json.loads((RUNTIME/'integration_examples/PH_SM_APPROVED_CONTENT_V1.example.json').read_text())
  release=original['payload']['release']
  package={'package_schema_version':'1.1.0','release_id':release['release_id'],'release_version':release['release_version'],
           'questions':original['payload']['questions'],'stimuli':original['payload']['stimuli']}
  content=integration.canonical_json(package).encode();content_sha=hashlib.sha256(content).hexdigest()
  manifest={'manifest_schema_version':'1.1.0','release_id':release['release_id'],'release_version':release['release_version'],
   'generated_at':'2026-10-27T00:00:00Z','content_file':'content.json','content_file_sha256':content_sha,
   'question_count':len(package['questions']),'stimulus_count':len(package['stimuli']),
   'files':[{'path':'content.json','size_bytes':len(content),'sha256':content_sha}]}
  manifest_bytes=integration.canonical_json(manifest).encode();buffer=io.BytesIO()
  with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as archive:
   archive.writestr('manifest.json',manifest_bytes);archive.writestr('content.json',content)
  data=buffer.getvalue();release=dict(release,package_checksum_sha256=hashlib.sha256(data).hexdigest(),
                                   manifest_checksum_sha256=hashlib.sha256(manifest_bytes).hexdigest())
  loaded,loaded_manifest=integration._load_manifest_package(data,release,'1.1.0')
  self.assertEqual(loaded,package);self.assertEqual(loaded_manifest,manifest)

if __name__=='__main__':unittest.main(verbosity=2)
