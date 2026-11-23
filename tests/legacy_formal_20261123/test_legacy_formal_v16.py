"""Differential native SQLite authority checks against the pinned V13 oracle."""
import ast
from copy import deepcopy
import hashlib
import importlib.machinery
import importlib.util
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
RUNTIME=ROOT/'scoremax_runtime_v669b'
sys.path.insert(0,str(RUNTIME))

def load(name,path):
    loader=importlib.machinery.SourceFileLoader(name,str(path))
    spec=importlib.util.spec_from_loader(name,loader)
    module=importlib.util.module_from_spec(spec);loader.exec_module(module)
    return module

old=load('formal_mask_v13_oracle',Path(__file__).with_name('fixtures')/'ph_mastery_evidence_v13.py.txt')
new=load('formal_mask_v16_candidate',RUNTIME/'ph_mastery_evidence.py')

class NativeFormalEvidenceDifferential(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'native.db'
        self.c=sqlite3.connect(self.path);self.c.row_factory=sqlite3.Row;self.addCleanup(self.c.close)
        self.c.executescript('''
CREATE TABLE questions(id INTEGER PRIMARY KEY,ph_projection_owner TEXT COLLATE NOCASE,
ph_question_id,ph_question_version_id,ph_question_checksum_sha256,active,status);
CREATE TABLE integration_ph_question_version_store(local_question_db_id,question_id,question_version_id,
question_checksum_sha256,scoremax_projection_json,content_json,curriculum_json);
CREATE TABLE integration_ph_release_question_membership(question_id,question_version_id,release_id,release_version);
CREATE TABLE integration_ph_content_releases(release_id,release_version,package_checksum_sha256,local_status,
market_id,programme_id,subject_id,chapter_id);
CREATE TABLE integration_ph_product_activation_authorizations(release_id,release_version,package_checksum_sha256,activation_status);
CREATE TABLE ph_bridge_staged_withdrawal_exclusions_v6611e(release_id,release_version,question_id,question_version_id);
''')
        owners=[None,'','LEGACY','power_house','Power_House','POWER_HOUSE ']
        self.c.executemany('INSERT INTO questions VALUES(?,?,?,?,?,?,?)',
            [(i,owners[i%len(owners)],None,None,None,i%2,'Rejected' if i%3 else 'Approved') for i in range(1,1501)])
        self.c.commit()

    def compare(self,records,programme='FSc Part 1'):
        before=deepcopy([dict(x) for x in records])
        expected=old.current_formal_evidence_mask(self.c,records,programme)
        actual=new.current_formal_evidence_mask(self.c,records,programme)
        self.assertEqual(actual,expected)
        self.assertEqual([dict(x) for x in records],before)
        return actual

    def test_real_300_and_1500_keys_duplicates_and_unknown_opaque_metadata(self):
        for count in [300,1500]:
            with self.subTest(count=count):
                records=[{'question_db_id':i,'future':{'opaque':'0001::Ω','nested':[True,None,{'n':i}]}}
                         for i in range(1,count+1)]
                records+=deepcopy(records[:7])
                self.assertEqual(self.compare(records),[True]*len(records))

    def test_binary_owner_comparison_preserves_native_python_semantics(self):
        records=[{'id':i} for i in range(1,16)]
        self.assertEqual(self.compare(records),[True]*15)
        self.c.execute("UPDATE questions SET ph_projection_owner='POWER_HOUSE' WHERE id=8")
        expected=[i!=8 for i in range(1,16)]
        self.assertEqual(self.compare(records),expected)

    def test_missing_key_is_individually_false_without_holding_other_evidence(self):
        records=[{'id':i} for i in range(1,1502)]
        self.assertEqual(self.compare(records),[True]*1500+[False])

    def test_internal_keys_are_not_coerced_from_opaque_external_strings(self):
        for bad in [True,False,'1','0001','opaque::1',1.0,0,-1,None]:
            with self.subTest(key=repr(bad)):
                self.assertEqual(self.compare([{'id':1},{'question_db_id':bad}]),[False,False])

    def test_record_ph_identity_never_enters_legacy_aggregate(self):
        for marker in ['PH::opaque::00001',True]:
            with self.subTest(marker=marker):
                self.assertEqual(self.compare([{'id':1,'ph_question_id':marker},{'id':2}]),[False,True])
        self.assertEqual(self.compare([{'id':1,'ph_question_id':''},{'id':2,'ph_question_id':None}]),[True,True])
        for module in (old,new):
            with self.subTest(invalid_identity_module=module.__name__):
                with self.assertRaises(TypeError):
                    module.current_formal_evidence_mask(self.c,[{'id':1,'ph_question_id':{'unfamiliar':'PH'}}],'FSc Part 1')
                self.assertFalse(self.c.in_transaction)

    def test_current_ph_owner_without_exact_membership_and_approval_stays_false(self):
        self.c.execute("UPDATE questions SET ph_projection_owner='POWER_HOUSE',ph_question_id='PH::new' WHERE id=2")
        self.assertEqual(self.compare([{'id':1},{'id':2}]),[True,False])
        self.assertEqual(self.compare([{'id':2,'ph_question_id':'PH::new','ph_release_id':'fake'}]),[False])

    def test_external_commit_rechecks_ownership_and_deletion_without_stale_proof(self):
        records=[{'id':1},{'id':2},{'id':3}]
        self.assertEqual(self.compare(records),[True]*3)
        other=sqlite3.connect(self.path)
        try:
            other.execute("UPDATE questions SET ph_projection_owner='POWER_HOUSE' WHERE id=2");other.commit()
            self.assertEqual(self.compare(records),[True,False,True])
            other.execute('DELETE FROM questions WHERE id=3');other.commit()
            self.assertEqual(self.compare(records),[True,False,False])
            other.execute("UPDATE questions SET ph_projection_owner=NULL WHERE id=2");other.commit()
            self.assertEqual(self.compare(records),[True,True,False])
        finally:other.close()

    def test_native_writer_sees_uncommitted_changes_and_keeps_its_transaction(self):
        self.c.execute('BEGIN IMMEDIATE')
        self.c.execute("UPDATE questions SET ph_projection_owner='POWER_HOUSE' WHERE id=1")
        self.assertEqual(self.compare([{'id':1},{'id':2}]),[False,True])
        self.assertTrue(self.c.in_transaction)
        self.c.rollback()
        self.assertEqual(self.compare([{'id':1},{'id':2}]),[True,True])

    def test_sqlite_rows_and_unknown_programme_preserve_original_gate(self):
        records=self.c.execute("SELECT id,'opaque::Ω' AS future FROM questions WHERE id<=7").fetchall()
        for programme in ['FSc Part 1','MDCAT','unfamiliar::programme',None]:
            with self.subTest(programme=programme):self.compare(records,programme)
        self.assertEqual(new.current_formal_evidence_mask(self.c,[],'MDCAT'),[])

    def test_aggregate_queries_are_bounded_and_do_not_mutate_native_state(self):
        traced=[];self.c.set_trace_callback(traced.append)
        try:self.assertEqual(new.current_formal_evidence_mask(self.c,[{'id':i} for i in range(1,1501)],'FSc Part 1'),[True]*1500)
        finally:self.c.set_trace_callback(None)
        selects=[x for x in traced if x.startswith('SELECT')]
        self.assertEqual(len(selects),3)
        self.assertTrue(all(x.startswith('SELECT COUNT(*)') for x in selects))
        self.assertTrue(all(x.startswith(('SELECT','SAVEPOINT','RELEASE')) for x in traced))
        self.assertFalse(self.c.in_transaction)

    def test_native_errors_propagate_and_savepoint_is_released(self):
        self.c.execute("UPDATE questions SET ph_projection_owner='POWER_HOUSE' WHERE id=1")
        self.c.execute('DROP TABLE integration_ph_content_releases');self.c.commit()
        for module in (old,new):
            with self.subTest(module=module.__name__):
                with self.assertRaises(sqlite3.OperationalError):module.current_formal_evidence_mask(self.c,[{'id':1}],'FSc Part 1')
                self.assertFalse(self.c.in_transaction)

    def test_all_existing_functions_and_the_full_ph_fallback_are_unchanged(self):
        before=ast.parse(Path(old.__file__).read_bytes());after=ast.parse(Path(new.__file__).read_bytes())
        function=next(n for n in after.body if isinstance(n,ast.FunctionDef) and n.name=='current_formal_evidence_mask')
        scope=next(n for n in function.body if isinstance(n,ast.Try))
        added=scope.body[1]
        self.assertIsInstance(added,ast.If)
        self.assertIn('all_legacy',ast.unparse(added))
        scope.body.remove(added)
        self.assertEqual(ast.dump(before,include_attributes=False),ast.dump(after,include_attributes=False))

if __name__=='__main__':unittest.main()
