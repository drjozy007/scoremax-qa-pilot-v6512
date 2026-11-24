"""Native chapter HTML parity plus auxiliary permission lease boundaries."""
import argparse,ast,copy,hashlib,json,os,sqlite3,sys
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'tests/biology_receiver_20261027'));sys.path.insert(0,str(ROOT))
from native_delivery_fixture import NativeDeliveryFixture

def function(path,name,namespace):
 node=next(n for n in ast.parse(path.read_text()).body if isinstance(n,ast.FunctionDef) and n.name==name);node.decorator_list=[]
 scope=dict(namespace);exec(compile(ast.Module(body=[node],type_ignores=[]),str(path),'exec'),scope);return scope[name]

def run(runtime,reference,state):
 f=NativeDeliveryFixture(runtime,state);sm=f.native
 import ux_content_reviewer as installed_reviewer
 installed_reviewer.install_content_reviewer(sm.app)
 import ux_catalogue_browser as catalogue
 catalogue.install_catalogue_browser(sm.app)
 old=function(reference/'app.py','chapter_page',sm.__dict__)
 import guided_fixture_helpers as guide
 source=ROOT/'scripts/qualify_assessment_contract_repair.py';ns={'copy':copy,'json':json}
 nodes=[n for n in ast.parse(source.read_text()).body if (isinstance(n,ast.FunctionDef) and n.name in ('question','rubric_question')) or (isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('RUBRIC','SPECS') for t in n.targets))]
 exec(compile(ast.Module(body=nodes,type_ignores=[]),str(source),'exec'),ns)
 uid=f.learner('chapter-parity');c=sm.db();columns={r[1] for r in c.execute('PRAGMA table_info(questions)')};counter=0;family_keys=[]
 def insert(q,chapter,topic,level):
  nonlocal counter
  counter+=1;q=copy.deepcopy(q);q.update(question_id='SOFTWARE-CHAPTER-'+str(counter),family_id='SOFTWARE-CHAPTER-FAMILY-'+str(counter),country='Pakistan',qualification='FSc Part 1',programme='FSc Part 1',subject='Biology',chapter=chapter,topic=topic,level=level,status='Approved',review_status='Approved',active=1,is_demo=0,source_type='SOFTWARE_ONLY')
  q['family_key']=sm.upsert_question_family(c,q,review_status='Approved',active=1);family_keys.append(q['family_key']);q={k:v for k,v in q.items() if k in columns};names=list(q);c.execute('INSERT INTO questions('+','.join(names)+') VALUES('+','.join('?' for _ in names)+')',[q[k] for k in names]);c.commit()
 for n,(name,(q,_)) in enumerate(ns['SPECS'].items()):
  for chapter in ('ordinary::α/000','mixed::opaque/001'):insert(q,chapter,None if n==0 else 'opaque/topic-'+str(n%3),'Foundation' if n%2 else 'Exam Ready')
 for chapter in ('guided::opaque/002','mixed::opaque/001'):
  insert(guide.fixture(),chapter,'guided/topic','Foundation');insert(guide.fixture(),chapter,'guided/topic','Advanced')
 cases=[]
 try:
  for stage in ('initial','family_hold','restored'):
   if stage=='family_hold':c.execute('UPDATE question_families SET active=0 WHERE family_key=?',(family_keys[0],));c.commit()
   if stage=='restored':c.execute('UPDATE question_families SET active=1 WHERE family_key=?',(family_keys[0],));c.commit()
   for chapter in ('empty::opaque/000','ordinary::α/000','guided::opaque/002','mixed::opaque/001'):
    def get(view):
     with patch.dict(sm.app.view_functions,{'chapter_page':view}),sm.app.test_client() as client:
      with client.session_transaction() as browser:browser.update(user_id=uid,role='student',session_version=0,_csrf_token='software-parity-csrf')
      response=client.get('/student/chapter',query_string={'subject':'Biology','chapter':chapter});assert response.status_code==200,(stage,chapter,response.status_code);return response.data
    a=get(old).replace(b'active scored questions',b'active questions');b=get(sm.chapter_page);assert a==b,('NATIVE_CHAPTER_HTML_DRIFT',stage,chapter)
    cases.append({'stage':stage,'chapter_kind':chapter.split('::')[0],'html_sha256':hashlib.sha256(b).hexdigest(),'byte_exact_native_parity':True})
  import ux_content_reviewer as reviewer
  from flask import session
  with sm.app.test_request_context('/student/chapter',method='GET'):
   session.update(role='student',user_id=uid)
   first=sm.db();raw=first._physical['connection'];first.close()
   borrowed=reviewer._connect();assert borrowed._physical['connection'] is raw;borrowed.close()
   assert reviewer._is_reviewer(uid) is False
   with closing(sqlite3.connect(f.state_directory/'native.db')) as writer,writer:writer.execute('UPDATE users SET content_reviewer_enabled=1 WHERE id=?',(uid,))
   assert reviewer._is_reviewer(uid) is True
   with closing(sqlite3.connect(f.state_directory/'native.db')) as writer,writer:writer.execute('UPDATE users SET content_reviewer_enabled=0 WHERE id=?',(uid,))
   assert reviewer._is_reviewer(uid) is False
  for path,method in (('/student/chapter','POST'),('/admin/backups','GET')):
   with sm.app.test_request_context(path,method=method):
    connection=reviewer._connect();assert type(connection) is sqlite3.Connection;connection.close()
  alternative=Path(state)/'alternate.db'
  with closing(sqlite3.connect(alternative)) as other,other:other.executescript('CREATE TABLE users(id PRIMARY KEY,content_reviewer_enabled); INSERT INTO users VALUES('+str(uid)+',0);')
  with sm.app.test_request_context('/student/chapter',method='GET'),patch.dict(os.environ,{'SCOREMAX_DB':str(alternative)}):
   session.update(role='student',user_id=uid);connection=reviewer._connect();assert type(connection) is sqlite3.Connection;connection.close();assert reviewer._is_reviewer(uid) is False
  assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok';assert not c.execute('PRAGMA foreign_key_check').fetchall()
 finally:c.close()
 return {'status':'PASSED','chapter_html_cases':cases,'permission_native_lease_reused':True,'fresh_permission_after_commit':True,'POST_and_other_routes_keep_original_connection':True,'alternate_DB_keeps_original_path':True,'authority':'SOFTWARE_FIXTURES_ONLY','production_actions':False}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('runtime',type=Path);p.add_argument('reference',type=Path);p.add_argument('state',type=Path);p.add_argument('output',type=Path);a=p.parse_args();r=run(a.runtime.resolve(),a.reference.resolve(),a.state.resolve());a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
