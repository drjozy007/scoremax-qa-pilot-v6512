from contextlib import closing
"""Actual native HTTP read + signed admission + submit + stop + SQLite backup.

Disposable derived data only. Full Power House ACK peer capacity is separate.
Reuses the unchanged primary HTTP timing harness and software envelope fixture.
"""
from pathlib import Path
import asyncio,hashlib,importlib.util,json,os,sqlite3,sys,time,urllib.parse
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'dependencies_v1'));sys.path.insert(0,str(ROOT/'tests/biology_receiver_20261027'))
from native_delivery_fixture import NativeDeliveryFixture
spec=importlib.util.spec_from_file_location('native_read_http_measurement',ROOT/'tests/navigation_current_20261123/benchmark_native_http_v4.py');b=importlib.util.module_from_spec(spec);spec.loader.exec_module(b)
original=b.workload
mixed=[]
writer_errors=[]

def original_rows(database):
 result={}
 with closing(sqlite3.connect(database)) as c:
  for table in b.PROTECTED:
   maximum=c.execute('SELECT COALESCE(MAX(rowid),0) FROM "'+table+'"').fetchone()[0]
   rows=c.execute('SELECT * FROM "'+table+'" WHERE rowid<=? ORDER BY rowid',(maximum,)).fetchall()
   result[table]=(maximum,hashlib.sha256(repr(rows).encode()).hexdigest(),len(rows))
 return result

def preserved(database,proof):
 with closing(sqlite3.connect(database)) as c:
  for table,(maximum,digest,n) in proof.items():
   rows=c.execute('SELECT * FROM "'+table+'" WHERE rowid<=? ORDER BY rowid',(maximum,)).fetchall()
   assert len(rows)==n and hashlib.sha256(repr(rows).encode()).hexdigest()==digest,('PREEXISTING_PROTECTED_ROWS_CHANGED',table)
  assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok';assert not c.execute('PRAGMA foreign_key_check').fetchall()

async def post(port,path,body,headers,expected):
 reader,writer=await asyncio.open_connection('127.0.0.1',port,limit=1024*1024)
 started=time.monotonic_ns()
 try:
  text='POST '+path+' HTTP/1.1\r\nHost: localhost\r\nConnection: close\r\nContent-Length: '+str(len(body))+'\r\n'+''.join(k+': '+v+'\r\n' for k,v in headers.items())+'\r\n'
  writer.write(text.encode()+body);await writer.drain();head=await asyncio.wait_for(reader.readuntil(b'\r\n\r\n'),45);payload=await reader.read();status=int(head.split(b' ',2)[1]);assert status in expected,(path,status,payload[:600]);mixed.append({'path':path,'status':status,'latency_ms':(time.monotonic_ns()-started)/1e6});return status
 finally:writer.close();await writer.wait_closed()

async def workload(port,route,cookies,level,operations,timeout,condition):
 sm=sys.modules['app'];db=Path(os.environ['SCOREMAX_DB']);proof=original_rows(db)
 f=object.__new__(NativeDeliveryFixture);f.native=sm;f.integration=sm.integration_v1;f.runtime_path=Path(sm.__file__).parent
 async def signed(path,e):
  i=f.integration;sent=i.utcnow();body=i.canonical_json(e).encode();headers={'Content-Type':'application/json','Authorization':'Bearer software-ph-token','X-Message-Id':e['message_id'],'X-Sent-At':sent,'X-Content-SHA256':e['payload_checksum_sha256'],'X-Signature':'hmac-sha256='+i.signature('POST',path,e['message_id'],sent,e['payload_checksum_sha256'],'software-ph-hmac')}
  return await post(port,path,body,headers,{200,202})
 async def write_and_backup():
  await asyncio.sleep(.1)
  e=f.content('mixed-native-http-v1');await signed('/api/integration/v1/power-house/content-releases',e);await signed('/api/integration/v1/power-house/content-releases',e)
  await asyncio.to_thread(f.activate,e)
  uid=await asyncio.to_thread(f.learner,'mixed-native-http-v1');sid,qid,programme=await asyncio.to_thread(f.session_for,uid,e)
  serializer=sm.app.session_interface.get_signing_serializer(sm.app);cookie=sm.app.config.get('SESSION_COOKIE_NAME','session')+'='+serializer.dumps({'user_id':uid,'role':'student','session_version':0,'_csrf_token':'software-fixture-csrf'})
  body=urllib.parse.urlencode({'_csrf_token':'software-fixture-csrf'}).encode();headers={'Content-Type':'application/x-www-form-urlencoded','Cookie':cookie}
  for _ in range(2):await post(port,'/test/session/'+str(sid)+'/submit',body,headers,{302})
  c=sm.db()
  try:
   attempts=c.execute('SELECT * FROM attempts WHERE assessment_session_id=?',(sid,)).fetchall();assert len(attempts)==1
   assert c.execute('SELECT COUNT(*) FROM attempt_answers WHERE attempt_id=?',(attempts[0]['id'],)).fetchone()[0]==1
   assert c.execute('SELECT COUNT(*) FROM mastery_records WHERE student_id=?',(uid,)).fetchone()[0]==0
   historical=tuple(attempts[0])
  finally:c.close()
  stop=f.withdrawal('mixed-native-stop-v1',e['payload']['questions'][0],target=f.exact_target(e));await signed('/api/integration/v1/power-house/question-withdrawals',stop);await signed('/api/integration/v1/power-house/question-withdrawals',stop)
  def backup():
   import shutil
   dest=db.parent.parent/'mixed-consistent-backup.db'
   assert not dest.exists() and shutil.disk_usage(dest.parent).free>2*db.stat().st_size+256*1024*1024
   with closing(sqlite3.connect(db.as_uri()+'?mode=ro',uri=True)) as source,closing(sqlite3.connect(dest)) as target:
    with target:source.backup(target,pages=500)
   with closing(sqlite3.connect(dest)) as c:assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok';assert not c.execute('PRAGMA foreign_key_check').fetchall()
   return dest.stat().st_size
  backup_bytes=await asyncio.to_thread(backup)
  c=sm.db()
  try:
   assert tuple(c.execute('SELECT * FROM attempts WHERE assessment_session_id=?',(sid,)).fetchone())==historical
   ledger=c.execute('SELECT contract_name,COUNT(*) FROM integration_outbox GROUP BY contract_name').fetchall()
   active=f.active(e['payload']['questions'][0]);assert active is None or not active['active'];assert c.execute('SELECT COUNT(*) FROM mastery_records WHERE student_id=?',(uid,)).fetchone()[0]==0
  finally:c.close()
  return {'actual_signed_ingress_and_duplicate':True,'native_activation_authorization':True,'actual_saved_answer_submit_and_duplicate':True,'native_attempts':1,'native_answers':1,'formal_mastery_rows_created':0,'signed_exact_withdrawal_and_duplicate':True,'historical_attempt_preserved':True,'sqlite_consistent_backup_bytes':backup_bytes,'native_outbox_contract_counts':{r[0]:r[1] for r in ledger},'full_PH_peer_ACK_under_load':'PENDING'}
 read_task=asyncio.create_task(original(port,route,cookies,level,operations,timeout,condition));write_task=asyncio.create_task(write_and_backup())
 results=await asyncio.gather(read_task,write_task,return_exceptions=True)
 if isinstance(results[0],BaseException):raise results[0]
 if isinstance(results[1],BaseException):
  writer_errors.append({'type':type(results[1]).__name__,'message':str(results[1])[:600]})
 else:
  try:preserved(db,proof)
  except Exception as error:writer_errors.append({'type':type(error).__name__,'message':str(error)[:600]})
  mixed.append({'native_writer_result':results[1],'preexisting_protected_tables_preserved':len(proof)})
 return results[0]

if __name__=='__main__':
 os.environ.update(POWER_HOUSE_TO_SCOREMAX_TOKEN='software-ph-token',POWER_HOUSE_TO_SCOREMAX_HMAC_SECRET='software-ph-hmac')
 b.workload=workload
 try:b.main()
 finally:
  # The primary read driver's full-table equality is expected to be false:
  # exact new native writer rows are proved above; original rows are preserved.
  out=Path(sys.argv[3]);dest=out.with_name(out.stem+'_mixed_actions.json');dest.write_text(json.dumps({'version':'SM-MIXED-NATIVE-HTTP-20261123-4','actions':mixed,'writer_errors':writer_errors,'production_actions':False,'real_source_authority':'SOFTWARE_FIXTURE_ONLY','mixed_driver_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},indent=2)+'\n')

 assert not writer_errors,writer_errors
