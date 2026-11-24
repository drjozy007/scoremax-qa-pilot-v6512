"""Exact V16 continuation: neutral practice labels preserve existing response modes."""
from pathlib import Path,PurePosixPath
import hashlib
import json

BASE_TREE='5746e20cbf82bf01655289c6f97f82863a8ff72cb1bc011d90e2fa39cc12083d'
AFTER_TREE='daf1071772cca3a5f23f5df7c89707e08a1b9399b3ad1d100ac23ec7b5e2deba'
DELTA_SHA='5ae0d9d0c8bd0368bf2c93374ac698d91c44820518ae9fef74a608ba59ca875c'
ALLOWED={'templates/test_setup.html'}

def digest(raw):return hashlib.sha256(raw).hexdigest()
def tree(root):
    rows={p.relative_to(root).as_posix():digest(p.read_bytes()) for p in root.rglob('*')
        if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
    return digest(json.dumps(rows,sort_keys=True,separators=(',',':')).encode())

def apply(root):
    root=Path(root).resolve(strict=True)
    current=tree(root)
    if current==AFTER_TREE:return {'policy':'SM-NEUTRAL-PRACTICE-LABEL-20261124-17','replayed':True,
        'after_tree_sha256':AFTER_TREE,'production_mutated':False,'official_ai_scoring_enabled':False}
    if current!=BASE_TREE:raise ValueError('PRACTICE_LABEL_EXACT_PRIOR_PENDING_RECEIVER_RUNTIME_REQUIRED')
    raw=Path(__file__).with_name('practice_label_delta_20261124_v17.json').read_bytes()
    if digest(raw)!=DELTA_SHA:raise ValueError('PRACTICE_LABEL_RECEIVER_DELTA_BYTES_DRIFT')
    data=json.loads(raw)
    if (data['before_tree_sha256']!=BASE_TREE or data['after_tree_sha256']!=AFTER_TREE
            or {r['path'] for r in data['files']}!=ALLOWED or len(data['files'])!=len(ALLOWED)):
        raise ValueError('PRACTICE_LABEL_RECEIVER_DELTA_SCOPE_DRIFT')
    prepared={}
    for row in data['files']:
        rel=PurePosixPath(row['path']);path=root.joinpath(*rel.parts)
        if rel.is_absolute() or '..' in rel.parts or path.is_symlink() or root not in path.resolve().parents:
            raise ValueError('PRACTICE_LABEL_RECEIVER_PATH_ESCAPE')
        if row['before_sha256'] is None:
            if path.exists():raise ValueError('PRACTICE_LABEL_NEW_CODE_PATH_EXISTS')
            text=row['new_file']
        else:
            before=path.read_bytes()
            if digest(before)!=row['before_sha256']:raise ValueError('PRACTICE_LABEL_NATIVE_SOURCE_DRIFT:'+row['path'])
            text=before.decode('utf8')
            for h in row['hunks']:
                if text.count(h['old'])!=1:raise ValueError('PRACTICE_LABEL_NATIVE_SOURCE_ANCHOR:'+row['path'])
                text=text.replace(h['old'],h['new'],1)
        after=text.encode('utf8')
        if digest(after)!=row['after_sha256']:raise ValueError('PRACTICE_LABEL_NATIVE_RESULT_DRIFT:'+row['path'])
        if path.suffix=='.py':compile(after,str(path),'exec')
        prepared[path]=after
    # Every input and output is checked before any code file changes.
    for path,raw in prepared.items():path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    if tree(root)!=AFTER_TREE:raise ValueError('PRACTICE_LABEL_RECEIVER_TREE_MISMATCH')
    return {'policy':'SM-NEUTRAL-PRACTICE-LABEL-20261124-17','before_tree_sha256':BASE_TREE,
        'after_tree_sha256':AFTER_TREE,'replayed':False,'database_tables_added':0,'automatic_schema_migration':False,
        'source_marks_and_weight_preserved':True,'production_mutated':False,'official_ai_scoring_enabled':False}
