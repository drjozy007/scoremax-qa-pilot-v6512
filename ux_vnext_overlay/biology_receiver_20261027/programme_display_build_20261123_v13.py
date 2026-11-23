"""Build-only exact continuation: retain all V10 paths except the cold chapter-count query."""
from pathlib import Path,PurePosixPath
import hashlib
import json

BASE_TREE='493fa68f06d4075ffdd92be504dc269e0e26c004c857ac4b77315403458fd0b6'
AFTER_TREE='b9c5a6c3e718668e0c0d1a2c924b25f66cb75b4cc97a6d5f50a48f50191af5a8'
DELTA_SHA='d63100f1f51d3a51022edccf2ba2c7e7c6f85284f52432d62f6f6546b39ff630'
ALLOWED={'app.py'}

def digest(raw):return hashlib.sha256(raw).hexdigest()
def tree(root):
    rows={p.relative_to(root).as_posix():digest(p.read_bytes()) for p in root.rglob('*')
        if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
    return digest(json.dumps(rows,sort_keys=True,separators=(',',':')).encode())

def apply(root):
    root=Path(root).resolve(strict=True)
    current=tree(root)
    if current==AFTER_TREE:return {'policy':'SM-BATCHED-PROGRAMME-PRESENCE-PREDICATE-ORDER-20261123-13','replayed':True,
        'after_tree_sha256':AFTER_TREE,'production_mutated':False,'official_ai_scoring_enabled':False}
    if current!=BASE_TREE:raise ValueError('PROGRAMME_DISPLAY_EXACT_PRIOR_PENDING_RECEIVER_RUNTIME_REQUIRED')
    raw=Path(__file__).with_name('programme_display_delta_20261123_v13.json').read_bytes()
    if digest(raw)!=DELTA_SHA:raise ValueError('PROGRAMME_DISPLAY_RECEIVER_DELTA_BYTES_DRIFT')
    data=json.loads(raw)
    if (data['before_tree_sha256']!=BASE_TREE or data['after_tree_sha256']!=AFTER_TREE
            or {r['path'] for r in data['files']}!=ALLOWED or len(data['files'])!=len(ALLOWED)):
        raise ValueError('PROGRAMME_DISPLAY_RECEIVER_DELTA_SCOPE_DRIFT')
    prepared={}
    for row in data['files']:
        rel=PurePosixPath(row['path']);path=root.joinpath(*rel.parts)
        if rel.is_absolute() or '..' in rel.parts or path.is_symlink() or root not in path.resolve().parents:
            raise ValueError('PROGRAMME_DISPLAY_RECEIVER_PATH_ESCAPE')
        if row['before_sha256'] is None:
            if path.exists():raise ValueError('PROGRAMME_DISPLAY_NEW_CODE_PATH_EXISTS')
            text=row['new_file']
        else:
            before=path.read_bytes()
            if digest(before)!=row['before_sha256']:raise ValueError('PROGRAMME_DISPLAY_NATIVE_SOURCE_DRIFT:'+row['path'])
            text=before.decode('utf8')
            for h in row['hunks']:
                if text.count(h['old'])!=1:raise ValueError('PROGRAMME_DISPLAY_NATIVE_SOURCE_ANCHOR:'+row['path'])
                text=text.replace(h['old'],h['new'],1)
        after=text.encode('utf8')
        if digest(after)!=row['after_sha256']:raise ValueError('PROGRAMME_DISPLAY_NATIVE_RESULT_DRIFT:'+row['path'])
        if path.suffix=='.py':compile(after,str(path),'exec')
        prepared[path]=after
    # Every input and output is checked before any code file changes.
    for path,raw in prepared.items():path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    if tree(root)!=AFTER_TREE:raise ValueError('PROGRAMME_DISPLAY_RECEIVER_TREE_MISMATCH')
    return {'policy':'SM-BATCHED-PROGRAMME-PRESENCE-PREDICATE-ORDER-20261123-13','before_tree_sha256':BASE_TREE,
        'after_tree_sha256':AFTER_TREE,'replayed':False,'database_tables_added':0,'automatic_schema_migration':False,
        'source_marks_and_weight_preserved':True,'production_mutated':False,'official_ai_scoring_enabled':False}
