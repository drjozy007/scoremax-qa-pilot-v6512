"""Assess SQLite index storage and governed question WRITE cost on disposable copies.

Never a production migration. Per-run BEGIN IMMEDIATE + ROLLBACK updates an
indexed subject column, verifies no row/state mutations survive, measures index
file size and approximate write amplification. Synthetic question data only.
"""
from __future__ import annotations
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import statistics
import sys
from time import perf_counter

MIGRATION_INDEX_PREFIX="idx_sm_nav_"
def dataset(path,expect_indexed):
    path=Path(path).resolve()
    if not path.is_file() or not path.is_relative_to(Path("/tmp")):
        raise RuntimeError("INDEX_WRITE_TEST_DISPOSABLE_ONLY")
    with closing(sqlite3.connect(path,timeout=6)) as c:
        c.execute("PRAGMA busy_timeout=6000")
        idx=c.execute("""SELECT name FROM sqlite_master
            WHERE type='index' AND name LIKE 'idx_sm_nav_%'""").fetchall()
        if (len(idx)>=5)!=expect_indexed:
            raise RuntimeError("INDEX_WRITE_FIXTURE_STATE_WRONG:"+repr(idx))
        n=c.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
        if n<100000:raise RuntimeError("INDEX_COST_REQUIRES_100K_BANK")
        page=c.execute("PRAGMA page_count").fetchone()[0]
        size=c.execute("PRAGMA page_size").fetchone()[0]
        freelist=c.execute("PRAGMA freelist_count").fetchone()[0]
        # Profile changing a subject used in the new indexes (not only
        # read-only fields), with exactly the same selected IDs in both DBs.
        selected=[r[0] for r in c.execute(
             "SELECT id FROM questions ORDER BY id LIMIT 2500")]
        if len(selected)!=2500:raise RuntimeError("INSUFFICIENT_WRITE_FIXTURE")
        original=c.execute("SELECT COUNT(*),SUM(LENGTH(subject)) FROM questions").fetchone()
        runs=[]
        for _ in range(4):
            t=perf_counter()
            c.execute("BEGIN IMMEDIATE")
            try:
                c.execute("""UPDATE questions
                   SET subject=CASE WHEN subject='Biology'
                     THEN 'SYN-INDEX-WRITE-COST' ELSE 'Biology' END
                   WHERE id IN (SELECT id FROM questions ORDER BY id LIMIT 2500)""")
                changed=c.execute("SELECT changes()").fetchone()[0]
                if changed!=2500:raise RuntimeError("DISPOSABLE_UPDATE_COUNT_WRONG")
            finally:
                c.rollback()
            runs.append(round((perf_counter()-t)*1000,3))
        after=c.execute("SELECT COUNT(*),SUM(LENGTH(subject)) FROM questions").fetchone()
        if tuple(original)!=tuple(after):
            raise RuntimeError("INDEX_TEST_LEFT_PERSISTENT_QUESTION_MUTATION")
        if c.execute("PRAGMA quick_check").fetchone()[0]!="ok":
            raise RuntimeError("INDEX_TEST_SQLITE_INTEGRITY_FAILED")
        return {"db_file_bytes":path.stat().st_size,
                "page_count":page,"page_size":size,"free_pages":freelist,
                "approx_pages_allocated_bytes":page*size,
                "questions":n,"indexed":expect_indexed,
                "source_index_count":len(idx),
                "rollback_update_2500_questions_ms":runs,
                "median_ms":round(statistics.median(runs),3),
                "questions_count_and_subject_lengths_unchanged":True}

def main(a,b):
    native=dataset(a,False)
    indexed=dataset(b,True)
    if native["questions"]!=indexed["questions"]:
        raise RuntimeError("INDEX_WRITE_SOURCE_CENSUS_MISMATCH")
    print("SCOREMAX_SQLITE_INDEX_WRITE_COST="+json.dumps({
      "without_indexes":native,"with_indexes":indexed,
      "write_update_cost_ratio":round(indexed["median_ms"]/max(0.1,native["median_ms"]),3),
      "disk_file_growth_bytes":indexed["db_file_bytes"]-native["db_file_bytes"],
      "additive_index_storage_not_free":True,
      "changes_per_trial":2500,"trials":4,
      "power_house_import_throughput_qualified":False,
      "no_production_db_access":True,
      "index_release_approved":False
    },sort_keys=True),flush=True)

if __name__=="__main__":
    if len(sys.argv)!=3:
        raise SystemExit("USAGE: script unindexed_disposable_db indexed_disposable_db")
    main(sys.argv[1],sys.argv[2])
