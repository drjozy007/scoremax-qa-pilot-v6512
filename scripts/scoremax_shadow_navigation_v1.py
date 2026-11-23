"""Optional governed visibility research reader: OFF by default, never marking authority.

A shadow row is usable only when source epoch, manifest epoch and programme
cardinality agree. Snapshot changes and eligibility mutations require guarded
atomic invalidation; any missing/broken/incomplete projection falls back to
the original native publication+Power House governance reader.
Production enablement requires independent signed-release/writer qualification.
"""
from __future__ import annotations
import os
import re
import sqlite3

SUPPORTED=("FSc Part 1","FSc Part 2","MDCAT","ECAT")
ENABLED="SCOREMAX_NAV_SHADOW_ENABLED"
QUERY="""SELECT m.subject subject,lower(m.subject) subject_key,
  m.chapter chapter,COUNT(*) question_count,MIN(m.question_db_id) first_id,
  mf.visible_count expected_visible_count
  FROM sm_shadow_visibility_member m
  JOIN sm_shadow_visibility_authority st ON st.id=1
  JOIN sm_shadow_visibility_manifest mf
    ON mf.programme=m.programme AND mf.snapshot_epoch=st.snapshot_epoch
  WHERE st.dirty=0 AND st.epoch=st.snapshot_epoch
    AND m.programme=?
    AND COALESCE(m.subject,'')<>''
  GROUP BY m.subject,m.chapter ORDER BY m.subject"""

def try_shadow_inventory(conn,programme):
    """Return exactly the native grouped-column shape, else native fallback."""
    if os.environ.get(ENABLED)!="1" or str(programme) not in SUPPORTED:
        return None
    try:
        rows=conn.execute(QUERY,(programme,)).fetchall()
        if not rows:return None
        # Grouped results cover every nonblank subject row. Detect a nonempty
        # but incomplete/corrupt projection, not merely an entirely empty one.
        total=sum(int(r["question_count"]) for r in rows)
        if any(int(r["expected_visible_count"])!=total for r in rows):
            return None
        return [{k:r[k] for k in (
            "subject","subject_key","chapter","question_count","first_id")} for r in rows]
    except (sqlite3.Error,KeyError,ValueError,TypeError):
        return None


def try_shadow_mastery_rows(conn,programme,clauses,parameters,columns):
    """Optional admission prefilter; native marking/mastery always authoritative.

    Pin the membership and integrity check to the SAME SQLite read transaction.
    Never rely on a programme-incomplete but nonempty shadow membership set.
    """
    if os.environ.get(ENABLED)!="1" or str(programme) not in SUPPORTED:
        return None
    if not isinstance(columns,(tuple,list)) or not columns or any(
        not isinstance(k,str) or re.fullmatch(r"[a-z][a-z_0-9]*",k) is None
        for k in columns
    ):
        return None
    if not isinstance(clauses,(tuple,list)) or not clauses:
        return None
    owns_read=False
    try:
        if not conn.in_transaction:
            conn.execute("BEGIN")
            owns_read=True
        select=",".join("q."+name for name in columns)
        where=" AND ".join(clauses)
        query=f"""SELECT {select} FROM questions q WHERE {where}
          AND EXISTS(
            SELECT 1 FROM sm_shadow_visibility_member sm
            JOIN sm_shadow_visibility_authority au
              ON au.id=1 AND au.dirty=0 AND au.epoch=au.snapshot_epoch
            JOIN sm_shadow_visibility_manifest mf
              ON mf.programme=sm.programme AND mf.snapshot_epoch=au.snapshot_epoch
            WHERE sm.programme=? AND sm.question_db_id=q.id
          )"""
        rows=conn.execute(query,list(parameters)+[programme]).fetchall()
        state=conn.execute("""SELECT au.dirty,au.epoch,au.snapshot_epoch,
                 mf.member_count,
                 (SELECT COUNT(*) FROM sm_shadow_visibility_member
                   WHERE programme=?) actual_member_count
              FROM sm_shadow_visibility_authority au
              LEFT JOIN sm_shadow_visibility_manifest mf
                 ON mf.programme=? AND mf.snapshot_epoch=au.snapshot_epoch
              WHERE au.id=1""",(programme,programme)).fetchone()
        if (not state or state["dirty"] or state["epoch"]!=state["snapshot_epoch"]
            or state["member_count"] is None
            or state["member_count"]!=state["actual_member_count"]):
            return None
        return rows
    except (sqlite3.Error,KeyError,ValueError,TypeError):
        return None
    finally:
        if owns_read:
            # Read-only transaction; releasing its pinned snapshot prevents
            # stale connection-level data from bleeding into subsequent calls.
            conn.rollback()
