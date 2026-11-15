"""Focused fail-closed tests for the disabled-by-default ScoreMax shadow reader."""
import importlib.util
import os
from pathlib import Path
import sqlite3
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
MOD=ROOT/"scripts/scoremax_shadow_navigation_v1.py"
spec=importlib.util.spec_from_file_location("sm_shadow_helper",MOD)
helper=importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)

class ShadowNavigationSafety(unittest.TestCase):
    def setUp(self):
        self.c=sqlite3.connect(":memory:")
        self.c.row_factory=sqlite3.Row
        self.c.executescript("""
          CREATE TABLE sm_shadow_visibility_authority(
             id INTEGER PRIMARY KEY,epoch INTEGER,dirty INTEGER,snapshot_epoch INTEGER);
          INSERT INTO sm_shadow_visibility_authority VALUES(1,3,0,3);
          CREATE TABLE sm_shadow_visibility_member(
             programme TEXT,question_db_id INTEGER,subject TEXT,chapter TEXT);
          INSERT INTO sm_shadow_visibility_member VALUES
             ('FSc Part 1',1,'Biology','Chapter A'),
             ('FSc Part 1',2,'Biology','Chapter A'),
             ('FSc Part 1',3,'BIOLOGY','Chapter B'),
             ('MDCAT',1,'Biology','OPAQUE::BIOLOGY::UNIT::14'),
             ('FSc Part 2',4,'Physics','Chapter 2');
        """)
    def tearDown(self):self.c.close()
    def get(self,programme="FSc Part 1",flag="1"):
        with patch.dict(os.environ,{"SCOREMAX_NAV_SHADOW_ENABLED":flag}):
            return helper.try_shadow_inventory(self.c,programme)
    def test_opt_in_required_no_cross_programme_leak(self):
        self.assertIsNone(self.get(flag="0"))
        self.assertIsNone(self.get("UNRECOGNISED"))
        self.assertEqual(sum(x["question_count"] for x in self.get()),3)
        mdcat=self.get("MDCAT")
        self.assertEqual(len(mdcat),1)
        self.assertEqual(mdcat[0]["chapter"],"OPAQUE::BIOLOGY::UNIT::14")
        self.assertEqual(mdcat[0]["question_count"],1)
    def test_native_sqlite_case_and_exact_chapter_grouping(self):
        rows=self.get()
        self.assertEqual([(x["subject"],x["chapter"],x["question_count"])
                          for x in rows],
                         [("BIOLOGY","Chapter B",1),("Biology","Chapter A",2)])
    def test_dirty_or_epoch_mismatch_fail_closed(self):
        self.c.execute("UPDATE sm_shadow_visibility_authority SET dirty=1")
        self.assertIsNone(self.get())
        self.c.execute("UPDATE sm_shadow_visibility_authority SET dirty=0,epoch=4")
        self.assertIsNone(self.get())
        self.c.execute("UPDATE sm_shadow_visibility_authority SET snapshot_epoch=4")
        self.assertEqual(sum(x["question_count"] for x in self.get()),3)
    def test_missing_or_corrupt_projection_never_leaks(self):
        self.c.execute("DROP TABLE sm_shadow_visibility_member")
        self.assertIsNone(self.get())
        self.c.execute("DROP TABLE sm_shadow_visibility_authority")
        self.assertIsNone(self.get())
    def test_no_cached_rows_uses_native_fallback(self):
        self.c.execute("DELETE FROM sm_shadow_visibility_member WHERE programme='FSc Part 1'")
        self.assertIsNone(self.get())

if __name__=="__main__":unittest.main()
