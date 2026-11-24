"""Native qualification-only controls; fixtures confer no academic authority."""
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import unittest

ROOT=Path(__file__).resolve().parents[2]
RUNTIME=Path(os.environ.get('SM_QUALIFICATION_RUNTIME',str(ROOT/'scoremax_runtime_v669b')))
spec=importlib.util.spec_from_file_location('tested_native_qualification',RUNTIME/'production_qualification_engine.py')
engine=importlib.util.module_from_spec(spec);spec.loader.exec_module(engine)


class SuccessorQualification(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(':memory:');self.c.row_factory=sqlite3.Row
        self.addCleanup(self.c.close)
        self.c.executescript('''
          CREATE TABLE questions(id INTEGER PRIMARY KEY,active INTEGER,status TEXT,content_environment TEXT,
            ph_projection_owner TEXT,ph_question_id TEXT,ph_question_version_id TEXT,ph_question_checksum_sha256 TEXT,
            ph_release_id TEXT,ph_release_version TEXT,ph_release_checksum_sha256 TEXT);
          CREATE TABLE integration_ph_content_releases(release_id TEXT,release_version TEXT,package_checksum_sha256 TEXT,
            local_status TEXT,question_count INTEGER,stimulus_count INTEGER,market_id TEXT,programme_id TEXT,subject_id TEXT,chapter_id TEXT);
          CREATE TABLE integration_ph_release_question_membership(id INTEGER PRIMARY KEY,release_id TEXT,release_version TEXT,
            ordinal INTEGER,question_id TEXT,question_version_id TEXT);
          CREATE TABLE integration_ph_question_version_store(question_id TEXT,question_version_id TEXT,question_checksum_sha256 TEXT,
            content_json TEXT,governance_json TEXT,local_question_db_id INTEGER);
          CREATE TABLE integration_ph_release_stimulus_membership(release_id TEXT,release_version TEXT,stimulus_id TEXT,stimulus_version_id TEXT);
          CREATE TABLE integration_ph_stimulus_version_store(stimulus_id TEXT,stimulus_version_id TEXT,stimulus_checksum_sha256 TEXT);
          CREATE TABLE integration_ph_product_activation_authorizations(release_id TEXT,release_version TEXT,
            package_checksum_sha256 TEXT,activation_status TEXT);
          CREATE TABLE ph_bridge_staged_withdrawal_exclusions_v6611e(release_id TEXT,release_version TEXT,question_id TEXT,question_version_id TEXT);
          CREATE TABLE integration_inbound_messages(idempotency_key TEXT,receive_count INTEGER);
        ''')
        self.c.executemany('INSERT INTO integration_ph_content_releases VALUES(?,?,?,?,?,0,?,?,?,?)',[
            ('release::opaque','prior::β','1'*64,'ACTIVE',2,'PK','FSC_PART_I','BIOLOGY','chapter::opaque'),
            ('release::opaque','successor::ζ','2'*64,'STAGED',3,'PK','FSC_PART_I','BIOLOGY','chapter::opaque')])
        self.c.execute('INSERT INTO integration_ph_product_activation_authorizations VALUES(?,?,?,?)',
            ('release::opaque','prior::β','1'*64,'ACTIVATED'))
        governance=json.dumps(dict(academic_review_state='APPROVED',hold_status='CLEAR',release_readiness='READY',r2_status='NOT_REQUIRED'))
        for i in range(1,4):
            qid=f'question::opaque::{i}';version=f'version::opaque::{i}';checksum=str(i+3)*64
            self.c.execute('INSERT INTO integration_ph_question_version_store VALUES(?,?,?,?,?,?)',
                (qid,version,checksum,json.dumps({'marking':{'key_type':'TEXT'}}),governance,i if i<3 else None))
            self.c.execute('INSERT INTO integration_ph_release_question_membership(release_id,release_version,ordinal,question_id,question_version_id) VALUES(?,?,?,?,?)',
                ('release::opaque','successor::ζ',i,qid,version))
            if i<3:
                self.c.execute('INSERT INTO integration_ph_release_question_membership(release_id,release_version,ordinal,question_id,question_version_id) VALUES(?,?,?,?,?)',
                    ('release::opaque','prior::β',i,qid,version))
                self.c.execute('INSERT INTO questions VALUES(?,1,?,?,?,?,?,?,?,?,?)',
                    (i,'Approved','PRODUCTION','POWER_HOUSE',qid,version,checksum,'release::opaque','prior::β','1'*64))
        engine.init_schema(self.c)

    def snapshot(self):
        return engine.snapshot(self.c,'release::opaque','successor::ζ','2'*64)

    def test_retained_exact_authorized_versions_do_not_block_new_staged_sibling(self):
        before=[tuple(r) for r in self.c.execute('SELECT * FROM questions ORDER BY id')]
        r=self.snapshot()
        self.assertEqual(r['status'],'PASS')
        self.assertEqual((r['learner_live_question_count'],r['staged_retained_authorized_live_question_count'],r['staged_unexpected_live_question_count']),(2,2,0))
        self.assertEqual(r['question_membership_count'],3)
        self.assertEqual(before,[tuple(r) for r in self.c.execute('SELECT * FROM questions ORDER BY id')])
        self.assertEqual(self.c.execute("SELECT local_status FROM integration_ph_content_releases WHERE release_version='successor::ζ'").fetchone()[0],'STAGED')

    def test_unapproved_actual_live_staged_content_is_still_a_hard_failure(self):
        self.c.execute("INSERT INTO questions VALUES(3,1,'Approved','PRODUCTION','POWER_HOUSE','question::opaque::3','version::opaque::3',?,'release::opaque','successor::ζ',?)",('6'*64,'2'*64))
        self.c.execute('UPDATE integration_ph_question_version_store SET local_question_db_id=3 WHERE question_id=?',('question::opaque::3',))
        r=self.snapshot()
        self.assertEqual(r['status'],'FAIL')
        self.assertIn('STAGED_RELEASE_LEAKED_LIVE',r['blocking_reasons'])
        self.assertEqual(r['staged_unexpected_live_question_count'],1)

    def test_every_existing_authority_and_exact_identity_link_is_required(self):
        mutations=[
          "DELETE FROM integration_ph_product_activation_authorizations",
          "UPDATE integration_ph_product_activation_authorizations SET activation_status='AUTHORIZED'",
          "UPDATE integration_ph_product_activation_authorizations SET package_checksum_sha256='wrong'",
          "UPDATE integration_ph_content_releases SET local_status='WITHDRAWN' WHERE release_version='prior::β'",
          "DELETE FROM integration_ph_release_question_membership WHERE release_version='prior::β'",
          "UPDATE questions SET ph_question_id='different' WHERE id=1",
          "UPDATE questions SET ph_question_version_id='different' WHERE id=1",
          "UPDATE questions SET ph_question_checksum_sha256='different' WHERE id=1",
          "UPDATE questions SET ph_release_version='different' WHERE id=1",
          "UPDATE questions SET ph_release_checksum_sha256='different' WHERE id=1",
          "UPDATE questions SET ph_projection_owner='OTHER' WHERE id=1",
          "UPDATE questions SET status='Rejected' WHERE id=1",
          "INSERT INTO ph_bridge_staged_withdrawal_exclusions_v6611e VALUES('release::opaque','prior::β','question::opaque::1','version::opaque::1')",
        ]
        for sql in mutations:
            with self.subTest(sql=sql):
                self.c.execute('SAVEPOINT attack');self.c.execute(sql)
                r=self.snapshot()
                self.assertIn('STAGED_RELEASE_LEAKED_LIVE',r['blocking_reasons'])
                self.c.execute('ROLLBACK TO attack');self.c.execute('RELEASE attack')

    def test_canonical_exact_version_reuse_across_programme_memberships_is_safe(self):
        self.c.execute("UPDATE integration_ph_content_releases SET programme_id='MDCAT',chapter_id='unit::opaque' WHERE release_version='successor::ζ'")
        r=self.snapshot()
        self.assertEqual(r['status'],'PASS')
        self.assertEqual(r['scope']['programme_id'],'MDCAT')
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM integration_ph_product_activation_authorizations').fetchone()[0],1)

    def test_projection_aliases_and_wrong_checksum_still_fail(self):
        self.c.execute("UPDATE integration_ph_question_version_store SET local_question_db_id=1 WHERE question_id='question::opaque::3'")
        self.assertIn('QUESTION_PROJECTION_IDENTITY_COLLISION',self.snapshot()['blocking_reasons'])
        self.assertIn('PACKAGE_CHECKSUM_MISMATCH',engine.snapshot(self.c,'release::opaque','successor::ζ','f'*64)['blocking_reasons'])

    def test_recorded_evidence_does_not_authorize_or_activate(self):
        r=engine.record_run(self.c,'release::opaque','successor::ζ','2'*64)
        self.assertEqual(r['status'],'PASS')
        self.assertEqual(len(engine.recent_runs(self.c)),1)
        self.assertEqual(self.c.execute('SELECT COUNT(*) FROM integration_ph_product_activation_authorizations').fetchone()[0],1)
        self.assertEqual(self.c.execute("SELECT local_status FROM integration_ph_content_releases WHERE release_version='successor::ζ'").fetchone()[0],'STAGED')

    def test_300_and_1500_retained_versions_use_bounded_lookups(self):
        for count in (300,1500):
            with self.subTest(count=count):
                self.c.execute('SAVEPOINT scale')
                governance=self.c.execute('SELECT governance_json FROM integration_ph_question_version_store LIMIT 1').fetchone()[0]
                for i in range(3,count+1):
                    qid=f'question::opaque::{i}';version=f'version::opaque::{i}'
                    checksum='6'*64 if i==3 else hashlib.sha256(qid.encode()).hexdigest()
                    if i==3:
                        self.c.execute('UPDATE integration_ph_question_version_store SET local_question_db_id=3 WHERE question_id=?',(qid,))
                    else:
                        self.c.execute('INSERT INTO integration_ph_question_version_store VALUES(?,?,?,?,?,?)',(qid,version,checksum,'{}',governance,i))
                        self.c.execute('INSERT INTO integration_ph_release_question_membership(release_id,release_version,ordinal,question_id,question_version_id) VALUES(?,?,?,?,?)',('release::opaque','successor::ζ',i,qid,version))
                    self.c.execute('INSERT INTO integration_ph_release_question_membership(release_id,release_version,ordinal,question_id,question_version_id) VALUES(?,?,?,?,?)',('release::opaque','prior::β',i,qid,version))
                    self.c.execute('INSERT INTO questions VALUES(?,1,?,?,?,?,?,?,?,?,?)',(i,'Approved','PRODUCTION','POWER_HOUSE',qid,version,checksum,'release::opaque','prior::β','1'*64))
                self.c.execute("UPDATE integration_ph_content_releases SET question_count=? WHERE release_version='successor::ζ'",(count,))
                queries=[];self.c.set_trace_callback(queries.append)
                r=self.snapshot();self.c.set_trace_callback(None)
                self.assertEqual((r['status'],r['staged_retained_authorized_live_question_count']),('PASS',count))
                self.assertLessEqual(sum(q.lstrip().upper().startswith('SELECT') for q in queries),20)
                self.c.execute('ROLLBACK TO scale');self.c.execute('RELEASE scale')


if __name__=='__main__':unittest.main()
