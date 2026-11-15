"""Fuse ScoreMax subject discovery and grouped chapter inventory in one governed query.

The previous optimised _subject_map performed two governed full-bank scans:
SELECT DISTINCT q.subject, then GROUP BY lower(q.subject),q.chapter. This
candidate uses one SELECT grouped by *exact* subject and chapter, reconstructs
both original result shapes, and never changes publication/PH scope semantics.

SQLite lower() and Python Unicode casefold differ; keep the original exact
subject order, SQL lowercase grouping, and Python .lower() lookup unchanged.
"""
from __future__ import annotations
import ast,hashlib,json
from pathlib import Path
from scoremax_navigation_grouped_scope_delta_20261114 import NEW_ANCHOR

MARKER="SCOREMAX_NAV_FUSED_SUBJECT_DISCOVERY_20261114"
OLD_LIVE='''    live_rows=c.execute(f"""SELECT DISTINCT q.subject FROM questions q
      WHERE {live_question_clause('q')} AND COALESCE(q.subject,'')<>'' AND {scope_clause}
      ORDER BY q.subject""",scope_params).fetchall()'''
NEW_LIVE='''    # SCOREMAX_NAV_FUSED_SUBJECT_DISCOVERY_20261114: retain exact subject
    # spelling/order, while grouping counts by SQLite lower(subject).
    inventory=c.execute(f"""SELECT q.subject subject,lower(q.subject) subject_key,
      q.chapter chapter,COUNT(*) question_count,MIN(q.id) first_id
      FROM questions q WHERE {live_question_clause('q')}
      AND COALESCE(q.subject,'')<>'' AND {scope_clause}
      GROUP BY q.subject,q.chapter ORDER BY q.subject""",scope_params).fetchall()
    live_rows=[]
    _seen_subjects=set()
    for _item in inventory:
        if _item['subject'] not in _seen_subjects:
            _seen_subjects.add(_item['subject'])
            live_rows.append({'subject':_item['subject']})'''
NEW_GROUP='''    # SCOREMAX_NAV_GROUPED_INVENTORY_20261114: one identical governed
    # publication predicate for every visible subject in the programme.
    # Preserve SQLite lower() subject grouping and case-sensitive chapter keys.
    scoped_counts={}
    _chapter_first={}
    for row in inventory:
        key=row['subject_key']
        scoped_counts[key]=scoped_counts.get(key,0)+int(row['question_count'] or 0)
        if row['chapter']:
            pair=(key,row['chapter'])
            old=_chapter_first.get(pair)
            if old is None or row['first_id']<old['first_id']:
                _chapter_first[pair]={'chapter':row['chapter'],'first_id':row['first_id']}
    scoped_chapters={}
    for (key,_chapter),item in _chapter_first.items():
        scoped_chapters.setdefault(key,[]).append(item)
    for chapters in scoped_chapters.values():
        chapters.sort(key=lambda item:item['first_id'])
    data=[]
    for subject in visible:
'''

def functions(src):
    return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(src).body
            if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}

def apply(root:Path):
    path=Path(root)/"app.py"
    before=path.read_text(encoding="utf8")
    tree=ast.parse(before)
    f=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="_subject_map"]
    if len(f)!=1:raise RuntimeError("FUSED_INVENTORY_SUBJECT_MAP_DRIFT")
    segment=ast.get_source_segment(before,f[0]) or ""
    if MARKER in segment:
        # The governed opt-in shadow successor wraps only the fused inventory
        # SELECT, preserving the native query as an indented fail-closed
        # fallback. Accept that exact marked successor, not arbitrary drift.
        shadow="SCOREMAX_NAV_SHADOW_OPTIN_20261115" in segment
        shadow_safe=(shadow and segment.count("SCOREMAX_NAV_SHADOW_OPTIN_20261115")==1
                     and "inventory=try_shadow_inventory(c,programme)" in segment
                     and "if inventory is None:" in segment
                     and "SELECT q.subject subject,lower(q.subject) subject_key" in segment)
        if (segment.count(MARKER)!=1 or NEW_GROUP not in segment
            or not (NEW_LIVE in segment or shadow_safe)):
            raise RuntimeError("FUSED_INVENTORY_PARTIAL_REPLAY")
        return {"status":"already_applied","read_only":True,"compatible_shadow":shadow_safe}
    if segment.count(OLD_LIVE)!=1 or segment.count(NEW_ANCHOR)!=1:
        raise RuntimeError("FUSED_INVENTORY_SOURCE_DRIFT")
    if "scoped_counts.get(subject.lower(),0)" not in segment or "scoped_chapters.get(display.lower(),[])" not in segment:
        raise RuntimeError("FUSED_INVENTORY_EXISTING_BOUNDS_DRIFT")
    if before.count(segment)!=1:raise RuntimeError("FUSED_INVENTORY_NONUNIQUE_SOURCE")
    updated=segment.replace(OLD_LIVE,NEW_LIVE,1).replace(NEW_ANCHOR,NEW_GROUP,1)
    after=before.replace(segment,updated,1)
    compile(after,str(path),"exec")
    a,b=functions(before),functions(after)
    if a.keys()!=b.keys() or any(a[k]!=b[k] for k in a if k!="_subject_map"):
        raise RuntimeError("FUSED_INVENTORY_UNRELATED_FUNCTION_CHANGE")
    path.write_text(after,encoding="utf8",newline="\n")
    return {"status":"applied","read_only":True,"no_schema_change":True,
            "no_publication_rule_change":True,"no_programme_rule_change":True,
            "before_sha256":hashlib.sha256(before.encode()).hexdigest(),
            "after_sha256":hashlib.sha256(after.encode()).hexdigest()}

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser();p.add_argument("runtime_root",type=Path)
    args=p.parse_args()
    print("SCOREMAX_FUSED_SUBJECT_INVENTORY="+json.dumps(apply(args.runtime_root),sort_keys=True))
