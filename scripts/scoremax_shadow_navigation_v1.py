"""Optional ScoreMax governed navigation inventory reader.

Disabled unless SCOREMAX_NAV_SHADOW_ENABLED=1. Source of truth stays native
questions/families/PH release membership/activation/withdrawal. This helper
never writes, never caches across HTTP requests, never bypasses per-student
commercial/mastery access, and never changes the academic marking contract.

One atomic SQL SELECT checks the persisted source/snapshot epochs AND reads
the indexed membership rows on the same SQLite statement snapshot.
Missing/stale/broken/empty scope falls back to the native read path.
"""
from __future__ import annotations
import os
import sqlite3

SUPPORTED=("FSc Part 1","FSc Part 2","MDCAT","ECAT")
ENABLED="SCOREMAX_NAV_SHADOW_ENABLED"
QUERY="""SELECT m.subject subject,lower(m.subject) subject_key,
  m.chapter chapter,COUNT(*) question_count,MIN(m.question_db_id) first_id
  FROM sm_shadow_visibility_member m
  JOIN sm_shadow_visibility_authority st ON st.id=1
  WHERE st.dirty=0 AND st.epoch=st.snapshot_epoch
    AND m.programme=?
    AND COALESCE(m.subject,'')<>''
  GROUP BY m.subject,m.chapter ORDER BY m.subject"""

def try_shadow_inventory(conn,programme):
    """Return native-shaped records if fresh; None means native fallback."""
    if os.environ.get(ENABLED)!="1" or str(programme) not in SUPPORTED:
        return None
    try:
        rows=conn.execute(QUERY,(programme,)).fetchall()
        # An empty match is ambiguous between zero eligible rows and stale
        # cache. Preserve authoritative native behavior in either case.
        if not rows:return None
        return [dict(r) for r in rows]
    except (sqlite3.OperationalError,sqlite3.DatabaseError,KeyError,ValueError,TypeError):
        # Never downgrade security: the caller must execute the original
        # publication+PH governance clauses if shadow cannot be proven fresh.
        return None



def try_shadow_mastery_rows(conn,programme,clauses,parameters,columns):
    """Optional governed programme prefilter for chapter-card mastery reads.

    Uses the SAME published visibility projection as student navigation.
    The source/snapshot epoch is joined IN THE SAME SELECT as membership;
    a second freshness check refuses a result invalidated during the call.
    None means fall back to the original full native programme-scope SQL.

    This never calculates mastery, authorises a release, or changes a learner
    response. The original live, calibration, demo, subject and chapter
    predicates are supplied unchanged by the accepted mastery reader.
    """
    import re
    if os.environ.get(ENABLED)!="1" or str(programme) not in SUPPORTED:
        return None
    # Only trusted q.column projections are legal; no dynamic SQL from user
    # chapter/subject text, which stays as bound SQLite parameters.
    if not isinstance(columns,(tuple,list)) or not columns or any(
        not isinstance(k,str) or re.fullmatch(r"[a-z][a-z_0-9]*",k) is None
        for k in columns
    ):
        return None
    if not isinstance(clauses,(tuple,list)) or not clauses:
        return None
    try:
        select=",".join("q."+name for name in columns)
        where=" AND ".join(clauses)
        query=f"""SELECT {select} FROM questions q WHERE {where}
          AND EXISTS(
          SELECT 1 FROM sm_shadow_visibility_member sm
          JOIN sm_shadow_visibility_authority au ON au.id=1
            AND au.dirty=0 AND au.epoch=au.snapshot_epoch
          WHERE sm.programme=? AND sm.question_db_id=q.id
          )"""
        rows=conn.execute(query,list(parameters)+[programme]).fetchall()
        # The source epoch can be dirtied by a concurrent writer between
        # statements. Reject the accelerated rows rather than trusting a
        # possibly stale view, so the caller reruns its native SQL.
        state=conn.execute("""SELECT dirty,epoch,snapshot_epoch
              FROM sm_shadow_visibility_authority WHERE id=1""").fetchone()
        if not state or state["dirty"] or state["epoch"]!=state["snapshot_epoch"]:
            return None
        return rows
    except (sqlite3.OperationalError,sqlite3.DatabaseError,KeyError,ValueError,TypeError):
        return None
