"""Adversarial tests for optional chapter-mastery visibility prefilter.

The production-like helper must never trust stale projections or another
programme's question membership; missing schema/dirty authority means native
fallback, not a guessed release or eligible mastery. All data is in-memory.
"""
from __future__ import annotations
import importlib.util
import os
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import patch

HELPER=Path(__file__).resolve().parents[2]/"scripts"/"scoremax_shadow_navigation_v1.py"
spec=importlib.util.spec_from_file_location("shadow_mastery_probe",HELPER)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class MasteryScopeProjection(unittest.TestCase):
    def setUp(self):
        self.conn=sqlite3.connect(":memory:")
        self.conn.row_factory=sqlite3.Row
        self.conn.executescript("""
        CREATE TABLE questions(id INTEGER PRIMARY KEY,subject TEXT,chapter TEXT,active INTEGER);
        CREATE TABLE sm_shadow_visibility_authority(
          id INTEGER PRIMARY KEY,dirty INTEGER,epoch INTEGER,snapshot_epoch INTEGER);
        CREATE TABLE sm_shadow_visibility_member(
          programme TEXT,question_db_id INTEGER,subject TEXT,chapter TEXT,
          PRIMARY KEY(programme,question_db_id));
        INSERT INTO questions VALUES(1,'Biology','Chapter 1',1);
        INSERT INTO questions VALUES(2,'Biology','Chapter 1',1);
        INSERT INTO questions VALUES(3,'Biology','Chapter 1',0);
        INSERT INTO questions VALUES(4,'Chemistry','Chapter 1',1);
        INSERT INTO sm_shadow_visibility_authority VALUES(1,0,4,4);
        INSERT INTO sm_shadow_visibility_member VALUES('FSc Part 1',1,'Biology','Chapter 1');
        INSERT INTO sm_shadow_visibility_member VALUES('MDCAT',2,'Biology','Chapter 1');
        INSERT INTO sm_shadow_visibility_member VALUES('FSc Part 1',4,'Chemistry','Chapter 1');
        """)
        self.clauses=["q.active=1","q.subject=?","q.chapter=?"]
        self.params=["Biology","Chapter 1"]
        self.columns=("id","subject","chapter")
    def tearDown(self):self.conn.close()
    def select(self,programme):
        with patch.dict(os.environ,{"SCOREMAX_NAV_SHADOW_ENABLED":"1"}):
            return module.try_shadow_mastery_rows(
                self.conn,programme,self.clauses,self.params,self.columns)
    def test_correct_programme_fresh(self):
        fsc=self.select("FSc Part 1")
        mdcat=self.select("MDCAT")
        self.assertEqual([x["id"] for x in fsc],[1])
        self.assertEqual([x["id"] for x in mdcat],[2])
    def test_dirty_invalidation_falls_back(self):
        self.conn.execute("UPDATE sm_shadow_visibility_authority SET dirty=1")
        self.assertIsNone(self.select("FSc Part 1"))
    def test_mismatched_epoch_falls_back(self):
        self.conn.execute("UPDATE sm_shadow_visibility_authority SET epoch=5")
        self.assertIsNone(self.select("FSc Part 1"))
    def test_absent_projection_falls_back(self):
        self.conn.execute("DROP TABLE sm_shadow_visibility_member")
        self.assertIsNone(self.select("FSc Part 1"))
    def test_optin_off_falls_back(self):
        with patch.dict(os.environ,{"SCOREMAX_NAV_SHADOW_ENABLED":"0"}):
            self.assertIsNone(module.try_shadow_mastery_rows(
                self.conn,"FSc Part 1",self.clauses,self.params,self.columns))
    def test_unsafe_projection_column_rejected(self):
        self.assertIsNone(module.try_shadow_mastery_rows(
            self.conn,"FSc Part 1",self.clauses,self.params,("id; DROP TABLE questions",)))
    def test_live_predicates_remain_required(self):
        self.conn.execute("UPDATE sm_shadow_visibility_member SET question_db_id=3 WHERE programme='FSc Part 1' AND question_db_id=1")
        self.assertEqual(len(self.select("FSc Part 1")),0)

if __name__=="__main__":unittest.main()
