"""ScoreMax learner-navigation batch scope counters (opt-in build-time delta).

Applied only after the sealed baseline and guarded evidence-index overlay.
It replaces repeated per-subject live-inventory COUNT and per-subject chapter
GROUP BY queries with ONE programme-scoped grouped query while preserving
the same live_question_clause and canonical subject-identity lookup.
No migration, no release/marking policy change, no cross-request cache.
"""
from __future__ import annotations
import ast,hashlib,json
from pathlib import Path

MARKER="SCOREMAX_NAV_GROUPED_INVENTORY_20261114"
OLD_ANCHOR="    data=[]\n    for subject in visible:\n"
NEW_ANCHOR="""    # SCOREMAX_NAV_GROUPED_INVENTORY_20261114: one identical governed
    # publication predicate for every visible subject in the programme.
    # Group by SQLite lower(), as in the original per-subject SQL predicates.
    inventory=c.execute(f""" + "'''" + """SELECT lower(q.subject) subject_key,q.chapter chapter,
      COUNT(*) question_count,MIN(q.id) first_id
      FROM questions q WHERE {live_question_clause('q')}
      AND COALESCE(q.subject,'')<>'' AND {scope_clause}
      GROUP BY lower(q.subject),q.chapter""" + "'''" + """,scope_params).fetchall()
    scoped_counts={}
    scoped_chapters={}
    for row in inventory:
        key=row['subject_key']
        scoped_counts[key]=scoped_counts.get(key,0)+int(row['question_count'] or 0)
        if row['chapter']:
            scoped_chapters.setdefault(key,[]).append(
              {'chapter':row['chapter'],'first_id':row['first_id']})
    for chapters in scoped_chapters.values():
        chapters.sort(key=lambda item:item['first_id'])
    # Use the database's own lower(), not Python Unicode lower/casefold.
    # This matches the original native WHERE lower(q.subject)=lower(?).
    _sqlite_subject_keys={}
    def _sqlite_subject_key(label):
        if label not in _sqlite_subject_keys:
            _sqlite_subject_keys[label]=c.execute('SELECT lower(?)',(label,)).fetchone()[0]
        return _sqlite_subject_keys[label]
    data=[]
    for subject in visible:
"""
OLD_COUNT="        qcount=c.execute(f\"SELECT COUNT(*) n FROM questions q WHERE {live_question_clause('q')} AND {subject_scope}\",params).fetchone()['n']"
NEW_COUNT="        qcount=scoped_counts.get(_sqlite_subject_key(subject),0)"
OLD_CHAPTER = '''        chapter_rows=c.execute(f"""SELECT q.chapter,MIN(q.id) first_id FROM questions q WHERE {live_question_clause('q')}
          AND {scope_clause} AND lower(q.subject)=lower(?) AND COALESCE(q.chapter,'')<>''
          GROUP BY q.chapter ORDER BY first_id""",scope_params+[display]).fetchall()'''
NEW_CHAPTER="        chapter_rows=scoped_chapters.get(_sqlite_subject_key(display),[])"

def apply(root:Path):
    path=Path(root)/"app.py"
    before=path.read_text(encoding="utf8")
    if MARKER in before:
        if before.count(MARKER)!=1 or NEW_COUNT not in before or NEW_CHAPTER not in before:
            raise RuntimeError("GROUPED_INVENTORY_PARTIAL_REPLAY")
        return {"status":"already_applied"}
    tree=ast.parse(before)
    nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="_subject_map"]
    if len(nodes)!=1:raise RuntimeError("GROUPED_INVENTORY_SUBJECT_MAP_DRIFT")
    fragment=ast.get_source_segment(before,nodes[0]) or ""
    for old in (OLD_ANCHOR,OLD_COUNT,OLD_CHAPTER):
        if fragment.count(old.strip("\n"))!=1 or before.count(old)!=1:
            raise RuntimeError("GROUPED_INVENTORY_SOURCE_DRIFT:"+old[:55])
    after=before.replace(OLD_ANCHOR,NEW_ANCHOR,1).replace(OLD_COUNT,NEW_COUNT,1).replace(OLD_CHAPTER,NEW_CHAPTER,1)
    compile(after,str(path),"exec")
    def fs(src):
        return {node.name:ast.dump(node,include_attributes=False) for node in ast.parse(src).body
                if isinstance(node,ast.FunctionDef)}
    oldfs,newfs=fs(before),fs(after)
    if oldfs.keys()!=newfs.keys() or any(oldfs[k]!=newfs[k] for k in oldfs if k!="_subject_map"):
        raise RuntimeError("GROUPED_INVENTORY_UNRELATED_CHANGE")
    path.write_text(after,encoding="utf8",newline="\n")
    return {"status":"applied","changes":["_subject_map"],"schema_change":False,
            "before_sha256":hashlib.sha256(before.encode()).hexdigest(),
            "after_sha256":hashlib.sha256(after.encode()).hexdigest()}

if __name__=="__main__":
    import argparse
    p=argparse.ArgumentParser();p.add_argument("runtime_root",type=Path);a=p.parse_args()
    print("SCOREMAX_NAV_INVENTORY_BATCH="+json.dumps(apply(a.runtime_root),sort_keys=True))
