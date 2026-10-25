"""Destination routing regression only. Disposable synthetic schema; no academic authority."""
import ast,json,sqlite3,sys,unittest
from pathlib import Path
source_path=sys.argv[1]
source=(Path(source_path)/'app.py').read_text()
sys.argv=sys.argv[:1]
names={'practice_scope_placements','practice_setup_context','_programme_subject_scope_sql','_programme_chapter_scope_sql'}
tree=ast.parse(source)
scope={'_programme_aliases':lambda p:[p],'canonical_programme':lambda p:p,
       '_programme_scope_sql':lambda aliases,table_alias='q':('1=1',[]),
       'live_question_clause':lambda a:a+".active=1 AND "+a+".status='Approved' AND "+a+".guided=0",
       'guided_live_question_clause':lambda a:a+".active=1 AND "+a+".status='Approved' AND "+a+".guided=1"}
exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in names],type_ignores=[]),'<actual-native-routing-functions>','exec'),scope)

class DestinationRoutingTests(unittest.TestCase):
 def setUp(self):
  self.c=sqlite3.connect(':memory:');self.c.row_factory=sqlite3.Row
  self.c.create_function('scoremax_release_programme',2,lambda p,c:p)
  self.c.executescript("""
  CREATE TABLE questions(id PRIMARY KEY,programme,qualification,subject,chapter,topic,ph_projection_owner,ph_question_id,ph_question_version_id,ph_question_checksum_sha256,active,status,guided);
  CREATE TABLE integration_ph_question_version_store(local_question_db_id,question_id,question_version_id,question_checksum_sha256,curriculum_json);
  CREATE TABLE integration_ph_release_question_membership(release_id,release_version,question_id,question_version_id);
  CREATE TABLE integration_ph_content_releases(release_id,release_version,programme_id,subject_id,chapter_id,local_status,package_checksum_sha256);
  CREATE TABLE integration_ph_product_activation_authorizations(release_id,release_version,package_checksum_sha256,activation_status);
  CREATE TABLE ph_bridge_staged_withdrawal_exclusions_v6611e(release_id,release_version,question_id,question_version_id);
  """)
  # One immutable Physics question, two approved curriculum destinations.
  self.c.execute("INSERT INTO questions VALUES(1,'FSc Part 2','FSc Part 2','Physics','13 — Thermal Physics','Gas law','POWER_HOUSE','Q1','V1','H1',1,'Approved',0)")
  self.c.execute("INSERT INTO integration_ph_question_version_store VALUES(1,'Q1','V1','H1','{}')")
  for rid,prog,sub,ch in [('FSC','FSc Part 2','PHYSICS','PHYSICS::12::13'),('MDCAT','MDCAT','CHEMISTRY','MDCAT::CHEMISTRY::UNIT::03')]:
   self.c.execute('INSERT INTO integration_ph_release_question_membership VALUES(?,?,?,?)',(rid,'1','Q1','V1'))
   self.c.execute('INSERT INTO integration_ph_content_releases VALUES(?,?,?,?,?,?,?)',(rid,'1',prog,sub,ch,'ACTIVE','P'+rid))
   self.c.execute('INSERT INTO integration_ph_product_activation_authorizations VALUES(?,?,?,?)',(rid,'1','P'+rid,'ACTIVATED'))
 def tearDown(self):self.c.close()
 def placed(self,p='MDCAT',guided=False):return scope['practice_scope_placements'](self.c,p,guided)
 def matches(self,kind,p,value):
  sql,args=scope['_programme_'+kind+'_scope_sql'](p,value,'q')
  return [r[0] for r in self.c.execute('SELECT q.id FROM questions q WHERE '+sql,args)]
 def test_cross_subject_projection_and_source_unchanged(self):
  before=dict(self.c.execute('SELECT * FROM questions').fetchone())
  self.assertEqual([(r['id'],r['subject'],r['chapter']) for r in self.placed()],[(1,'Chemistry','MDCAT::CHEMISTRY::UNIT::03')])
  self.assertEqual([(r['subject'],r['chapter']) for r in self.placed('FSc Part 2')],[('Physics','13 — Thermal Physics')])
  self.assertEqual(before,dict(self.c.execute('SELECT * FROM questions').fetchone()))
 def test_subject_and_unit_never_fall_back_to_source(self):
  self.assertEqual(self.matches('subject','MDCAT','Chemistry'),[1])
  self.assertEqual(self.matches('subject','MDCAT','Physics'),[])
  self.assertEqual(self.matches('chapter','MDCAT','MDCAT::CHEMISTRY::UNIT::03'),[1])
  self.assertEqual(self.matches('chapter','MDCAT','13 — Thermal Physics'),[])
 def test_missing_authority_withdrawal_and_wrong_hash_fail_closed(self):
  self.c.execute("DELETE FROM integration_ph_product_activation_authorizations WHERE release_id='MDCAT'")
  self.assertEqual(self.placed(),[]);self.assertEqual(self.matches('subject','MDCAT','Chemistry'),[])
  self.c.execute("INSERT INTO integration_ph_product_activation_authorizations VALUES('MDCAT','1','PMDCAT','ACTIVATED')")
  self.c.execute("INSERT INTO ph_bridge_staged_withdrawal_exclusions_v6611e VALUES('MDCAT','1','Q1','V1')")
  self.assertEqual(self.placed(),[]);self.assertEqual(self.matches('subject','MDCAT','Chemistry'),[])
  self.c.execute('DELETE FROM ph_bridge_staged_withdrawal_exclusions_v6611e')
  self.c.execute("UPDATE questions SET ph_question_checksum_sha256='TAMPERED'")
  self.assertEqual(self.placed(),[]);self.assertEqual(self.matches('subject','MDCAT','Chemistry'),[])
 def test_inactive_held_and_guided_modes_stay_separate(self):
  self.c.execute("UPDATE questions SET status='HELD'");self.assertEqual(self.placed(),[])
  self.c.execute("UPDATE questions SET status='Approved',active=0");self.assertEqual(self.placed(),[])
  self.c.execute("UPDATE questions SET active=1,guided=1");self.assertEqual(self.placed(),[])
  self.assertEqual(len(self.placed(guided=True)),1)
 def test_destination_entitlements_do_not_inherit_source_subject(self):
  engine=ast.parse((Path(__file__).resolve().parent/'commercial_source.py').read_text()) if False else None
  # Execute the exact production commercial function, with only the aliases dependency stubbed.
  import types
  module=types.ModuleType('question_contract_engine');module.programme_aliases=lambda p:[p]
  previous=sys.modules.get('question_contract_engine');sys.modules['question_contract_engine']=module
  try:
   text=COMMERCIAL_SOURCE
   local={};exec(compile(ast.Module(body=[n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name=='programme_subjects'],type_ignores=[]),'<actual-commercial-function>','exec'),local)
   self.assertEqual(local['programme_subjects'](self.c,'MDCAT'),['Chemistry'])
   self.assertEqual(local['programme_subjects'](self.c,'FSc Part 2'),['Physics'])
  finally:
   if previous is None:sys.modules.pop('question_contract_engine',None)
   else:sys.modules['question_contract_engine']=previous
COMMERCIAL_SOURCE=(Path(__file__).resolve().parent/'commercial_source.py').read_text() if False else (Path(source_path)/'commercial_access_engine.py').read_text()
if __name__=='__main__':unittest.main()
