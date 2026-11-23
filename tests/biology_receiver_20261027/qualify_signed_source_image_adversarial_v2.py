"""Native resealed bad-image inputs produce durable, idempotent rejection."""
from pathlib import Path
from copy import deepcopy
import argparse,hashlib,json,sys,tempfile,base64
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tests/biology_receiver_20261027'))
from native_delivery_fixture import NativeDeliveryFixture
PNG=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=')
mutations=[('HTTP_URI',{'uri':'https://example.invalid/image.png'}),('SVG_URI',{'uri':'data:image/svg+xml;base64,PHN2Zy8+'}),('JS_URI',{'uri':'javascript:alert(1)'}),('LOCAL_FILE_URI',{'uri':'file:///private.png'}),('WRONG_IMAGE_HASH',{'file_sha256':'0'*64}),('WRONG_MIME',{'mime_type':'image/jpeg'}),('CORRUPT_IMAGE',{'uri':'data:image/png;base64,AAAA','file_sha256':hashlib.sha256(b'\0\0\0').hexdigest()}),('OVERSIZE_URI',{'uri':'data:image/png;base64,'+'A'*(2_000_000*4//3+101)})]

def run(runtime):
 cases=[]
 with tempfile.TemporaryDirectory(prefix='signed-source-image-attacks-') as directory:
  f=NativeDeliveryFixture(runtime,directory)
  from pending_saq_software_fixture_20261122 import content
  for label,changes in mutations:
   e=content(f,'image-attack-'+label,2);q=e['payload']['questions'][0];stim={'stimulus_id':'opaque::attack-image/'+label,'stimulus_version_id':'opaque::attack-version/'+label,'stimulus_type':'IMAGE_REFERENCE','content':{'uri':'data:image/png;base64,'+base64.b64encode(PNG).decode(),'file_sha256':hashlib.sha256(PNG).hexdigest(),'mime_type':'image/png'},'provenance':deepcopy(q['provenance']['primary_source'])};stim['content'].update(changes);stim['stimulus_checksum_sha256']=f.integration._object_checksum(stim,'stimulus_checksum_sha256');q['content']['stimulus_ref']=stim['stimulus_id'];q['question_checksum_sha256']=f.integration._object_checksum(q,'question_checksum_sha256');e['payload']['stimuli']=[stim];e['payload']['release']['stimulus_count']=1;f.seal(e)
   status,result=f.signed_post('/api/integration/v1/power-house/content-releases',e,expected_statuses=(422,));again,replayed=f.signed_post('/api/integration/v1/power-house/content-releases',e,expected_statuses=(422,));assert result['receipt_id']==replayed['receipt_id'] and result['status']=='REJECTED';row=f.active(q);assert not row or not row['active']
   c=f.native.db()
   try:
    recorded=c.execute('SELECT status,receive_count,receipt_id FROM integration_inbound_messages WHERE message_id=?',(e['message_id'],)).fetchone();assert recorded['status']=='REJECTED' and recorded['receive_count']==2 and recorded['receipt_id']==result['receipt_id']
    assert c.execute('SELECT COUNT(*) FROM integration_ph_question_version_store WHERE question_id=?',(q['question_id'],)).fetchone()[0]==0
   finally:c.close()
   cases.append({'case':label,'status':status,'learner_active':False,'same_durable_rejection_after_retry':True,'immutable_question_version_written':False})
 return {'status':'PASSED_NATIVE_SIGNED_IMAGE_DURABLE_REJECTION','cases':cases,'payload_question_stimulus_and_HMAC_resealed':True,'production_mutated':False}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('runtime',type=Path);p.add_argument('output',type=Path);a=p.parse_args();r=run(a.runtime.resolve());assert not a.output.exists();a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
