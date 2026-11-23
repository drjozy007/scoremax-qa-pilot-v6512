"""Build-only continuation of the existing source-delta materializer."""
from pathlib import Path,PurePosixPath
import hashlib
import json

BASE_TREE='51a17d3c7ee32031f1555dcfb98564bf9ebbaa877462af2a4954029121ce0869'
AFTER_TREE='723ebb01fec680db2e88c9159deeac74b941cf4be8e5ab7d95b6691a3afb5bff'
DELTA_SHA='c47757e67f3ce3f26df21802a02a20f84972eb76c6768610677d96c6d905bd13'
ALLOWED={'templates/_ph_learner_stimulus_image.html', 'app.py', 'templates/result.html', 'ph_learner_media_v1.py', 'templates/_learner_question_surface.html', 'scoremax_integration_v1.py'}

def digest(raw):return hashlib.sha256(raw).hexdigest()
def tree(root):
    rows={p.relative_to(root).as_posix():digest(p.read_bytes()) for p in root.rglob('*')
        if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
    return digest(json.dumps(rows,sort_keys=True,separators=(',',':')).encode())

def apply(root):
    root=Path(root).resolve(strict=True)
    current=tree(root)
    if current==AFTER_TREE:return {'policy':'SM-NATIVE-LEARNER-STIMULUS-IMAGE-20261123-5','replayed':True,
        'after_tree_sha256':AFTER_TREE,'production_mutated':False,'official_ai_scoring_enabled':False}
    if current!=BASE_TREE:raise ValueError('WORK_B_EXACT_PRIOR_SCORED_RUNTIME_REQUIRED')
    raw=Path(__file__).with_name('work_b_receiver_delta_20261123_v5.json').read_bytes()
    if digest(raw)!=DELTA_SHA:raise ValueError('WORK_B_RECEIVER_DELTA_BYTES_DRIFT')
    data=json.loads(raw)
    if (data['before_tree_sha256']!=BASE_TREE or data['after_tree_sha256']!=AFTER_TREE
            or {r['path'] for r in data['files']}!=ALLOWED or len(data['files'])!=len(ALLOWED)):
        raise ValueError('WORK_B_RECEIVER_DELTA_SCOPE_DRIFT')
    prepared={}
    for row in data['files']:
        rel=PurePosixPath(row['path']);path=root.joinpath(*rel.parts)
        if rel.is_absolute() or '..' in rel.parts or path.is_symlink() or root not in path.resolve().parents:
            raise ValueError('WORK_B_RECEIVER_PATH_ESCAPE')
        if row['before_sha256'] is None:
            if path.exists():raise ValueError('WORK_B_NEW_CODE_PATH_EXISTS')
            text=row['new_file']
        else:
            before=path.read_bytes()
            if digest(before)!=row['before_sha256']:raise ValueError('WORK_B_NATIVE_SOURCE_DRIFT:'+row['path'])
            text=before.decode('utf8')
            for h in row['hunks']:
                if text.count(h['old'])!=1:raise ValueError('WORK_B_NATIVE_SOURCE_ANCHOR:'+row['path'])
                text=text.replace(h['old'],h['new'],1)
        after=text.encode('utf8')
        if digest(after)!=row['after_sha256']:raise ValueError('WORK_B_NATIVE_RESULT_DRIFT:'+row['path'])
        if path.suffix=='.py':compile(after,str(path),'exec')
        prepared[path]=after
    # Every input and output is checked before any code file changes.
    for path,raw in prepared.items():path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    if tree(root)!=AFTER_TREE:raise ValueError('WORK_B_RECEIVER_TREE_MISMATCH')
    return {'policy':'SM-NATIVE-LEARNER-STIMULUS-IMAGE-20261123-5','before_tree_sha256':BASE_TREE,
        'after_tree_sha256':AFTER_TREE,'replayed':False,'database_tables_added':0,
        'source_marks_and_weight_preserved':True,'production_mutated':False,'official_ai_scoring_enabled':False}


def rollback_build_only(root):
    """Reverse only exact source bytes in disposable build tests, never database state.

    After image-bearing publication, the operational rollback floor retains
    this image-capable receiver so historical attempt figures remain available.
    """
    root=Path(root).resolve(strict=True)
    if tree(root)!=AFTER_TREE:raise ValueError('WORK_B_EXACT_IMAGE_BUILD_ROLLBACK_REQUIRED')
    raw=Path(__file__).with_name('work_b_receiver_delta_20261123_v5.json').read_bytes()
    if digest(raw)!=DELTA_SHA:raise ValueError('WORK_B_RECEIVER_DELTA_BYTES_DRIFT')
    data=json.loads(raw);prepared={}
    for row in data['files']:
        path=root/row['path'];raw=path.read_bytes()
        if digest(raw)!=row['after_sha256']:raise ValueError('WORK_B_ROLLBACK_SOURCE_DRIFT')
        if row['before_sha256'] is None:prepared[path]=None;continue
        text=raw.decode()
        for h in reversed(row['hunks']):
            if text.count(h['new'])!=1:raise ValueError('WORK_B_ROLLBACK_SOURCE_ANCHOR')
            text=text.replace(h['new'],h['old'],1)
        raw=text.encode()
        if digest(raw)!=row['before_sha256']:raise ValueError('WORK_B_ROLLBACK_RESULT_DRIFT')
        prepared[path]=raw
    for path,raw in prepared.items():
        if raw is None:path.unlink()
        else:path.write_bytes(raw)
    if tree(root)!=BASE_TREE:raise ValueError('WORK_B_ROLLBACK_TREE_DRIFT')
    return {'build_source_rollback':'PASSED','production_rollback_authority':False,'database_mutated':False}
