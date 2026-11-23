"""Build-only exact continuation: retain all V10 paths except the cold chapter-count query."""
from pathlib import Path,PurePosixPath
import hashlib
import json

BASE_TREE='d0fc1c5d46d793e3a86161a9f2b6fe6e5991160f1e38a54324cb95c60f3c64c8'
AFTER_TREE='493fa68f06d4075ffdd92be504dc269e0e26c004c857ac4b77315403458fd0b6'
DELTA_SHA='1ac242e75667fd2224af7a434b4f5a6249cea63bf5b8e79b26d3f658f7a85fee'
ALLOWED={'ux_student_batch.py'}

def digest(raw):return hashlib.sha256(raw).hexdigest()
def tree(root):
    rows={p.relative_to(root).as_posix():digest(p.read_bytes()) for p in root.rglob('*')
        if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
    return digest(json.dumps(rows,sort_keys=True,separators=(',',':')).encode())

def apply(root):
    root=Path(root).resolve(strict=True)
    current=tree(root)
    if current==AFTER_TREE:return {'policy':'SM-WEIGHTED-NATIVE-CHAPTER-COUNTS-20261123-11','replayed':True,
        'after_tree_sha256':AFTER_TREE,'production_mutated':False,'official_ai_scoring_enabled':False}
    if current!=BASE_TREE:raise ValueError('WEIGHTED_CHAPTER_EXACT_PRIOR_PENDING_RECEIVER_RUNTIME_REQUIRED')
    raw=Path(__file__).with_name('weighted_chapter_delta_20261123_v11.json').read_bytes()
    if digest(raw)!=DELTA_SHA:raise ValueError('WEIGHTED_CHAPTER_RECEIVER_DELTA_BYTES_DRIFT')
    data=json.loads(raw)
    if (data['before_tree_sha256']!=BASE_TREE or data['after_tree_sha256']!=AFTER_TREE
            or {r['path'] for r in data['files']}!=ALLOWED or len(data['files'])!=len(ALLOWED)):
        raise ValueError('WEIGHTED_CHAPTER_RECEIVER_DELTA_SCOPE_DRIFT')
    prepared={}
    for row in data['files']:
        rel=PurePosixPath(row['path']);path=root.joinpath(*rel.parts)
        if rel.is_absolute() or '..' in rel.parts or path.is_symlink() or root not in path.resolve().parents:
            raise ValueError('WEIGHTED_CHAPTER_RECEIVER_PATH_ESCAPE')
        if row['before_sha256'] is None:
            if path.exists():raise ValueError('WEIGHTED_CHAPTER_NEW_CODE_PATH_EXISTS')
            text=row['new_file']
        else:
            before=path.read_bytes()
            if digest(before)!=row['before_sha256']:raise ValueError('WEIGHTED_CHAPTER_NATIVE_SOURCE_DRIFT:'+row['path'])
            text=before.decode('utf8')
            for h in row['hunks']:
                if text.count(h['old'])!=1:raise ValueError('WEIGHTED_CHAPTER_NATIVE_SOURCE_ANCHOR:'+row['path'])
                text=text.replace(h['old'],h['new'],1)
        after=text.encode('utf8')
        if digest(after)!=row['after_sha256']:raise ValueError('WEIGHTED_CHAPTER_NATIVE_RESULT_DRIFT:'+row['path'])
        if path.suffix=='.py':compile(after,str(path),'exec')
        prepared[path]=after
    # Every input and output is checked before any code file changes.
    for path,raw in prepared.items():path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    if tree(root)!=AFTER_TREE:raise ValueError('WEIGHTED_CHAPTER_RECEIVER_TREE_MISMATCH')
    return {'policy':'SM-WEIGHTED-NATIVE-CHAPTER-COUNTS-20261123-11','before_tree_sha256':BASE_TREE,
        'after_tree_sha256':AFTER_TREE,'replayed':False,'database_tables_added':0,'automatic_schema_migration':False,
        'source_marks_and_weight_preserved':True,'production_mutated':False,'official_ai_scoring_enabled':False}
