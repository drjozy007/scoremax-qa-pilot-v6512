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
