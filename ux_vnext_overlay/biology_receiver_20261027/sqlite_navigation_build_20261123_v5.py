"""Build-only continuation of the existing source-delta materializer."""
from pathlib import Path,PurePosixPath
import hashlib
import json

BASE_TREE='6752a39993549833d59bf055601304cc4b69a06d37c509a5d36b11f31d21bcb3'
AFTER_TREE='29dedc32570700fdb9fa303b8678d72eac9d3e370ef6150276635f331fd80cc0'
DELTA_SHA='b43f169bf78081a2e6ada4f5d561eb450d0dfc6b3a2b2538c5522ec5d27f84d2'
ALLOWED={'navigation_request_connections_v1.py', 'app.py', 'navigation_display_inventory_v3.py', 'commercial_access_engine.py', 'ux_student_batch.py', 'frozen_context_decode_v4.py', 'ux_catalogue_browser.py', 'ux_content_reviewer.py', 'navigation_display_reads_v5.py', 'question_contract_engine.py', 'ux_staging_routes.py', 'sqlite_mutation_engine.py', 'ph_mastery_evidence.py'}

def digest(raw):return hashlib.sha256(raw).hexdigest()
def tree(root):
    rows={p.relative_to(root).as_posix():digest(p.read_bytes()) for p in root.rglob('*')
        if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
    return digest(json.dumps(rows,sort_keys=True,separators=(',',':')).encode())

def apply(root):
    root=Path(root).resolve(strict=True)
    current=tree(root)
    if current==AFTER_TREE:return {'policy':'SM-SQLITE-NAV-IMAGE-COMPOSITION-20261123-5','replayed':True,
        'after_tree_sha256':AFTER_TREE,'production_mutated':False,'official_ai_scoring_enabled':False}
    if current!=BASE_TREE:raise ValueError('SQLITE_NAV_EXACT_PRIOR_PENDING_RECEIVER_RUNTIME_REQUIRED')
    raw=Path(__file__).with_name('sqlite_navigation_delta_20261123_v5.json').read_bytes()
    if digest(raw)!=DELTA_SHA:raise ValueError('SQLITE_NAV_RECEIVER_DELTA_BYTES_DRIFT')
    data=json.loads(raw)
    if (data['before_tree_sha256']!=BASE_TREE or data['after_tree_sha256']!=AFTER_TREE
            or {r['path'] for r in data['files']}!=ALLOWED or len(data['files'])!=len(ALLOWED)):
        raise ValueError('SQLITE_NAV_RECEIVER_DELTA_SCOPE_DRIFT')
    prepared={}
    for row in data['files']:
        rel=PurePosixPath(row['path']);path=root.joinpath(*rel.parts)
        if rel.is_absolute() or '..' in rel.parts or path.is_symlink() or root not in path.resolve().parents:
            raise ValueError('SQLITE_NAV_RECEIVER_PATH_ESCAPE')
        if row['before_sha256'] is None:
            if path.exists():raise ValueError('SQLITE_NAV_NEW_CODE_PATH_EXISTS')
            text=row['new_file']
        else:
            before=path.read_bytes()
            if digest(before)!=row['before_sha256']:raise ValueError('SQLITE_NAV_NATIVE_SOURCE_DRIFT:'+row['path'])
            text=before.decode('utf8')
            for h in row['hunks']:
                if text.count(h['old'])!=1:raise ValueError('SQLITE_NAV_NATIVE_SOURCE_ANCHOR:'+row['path'])
                text=text.replace(h['old'],h['new'],1)
        after=text.encode('utf8')
        if digest(after)!=row['after_sha256']:raise ValueError('SQLITE_NAV_NATIVE_RESULT_DRIFT:'+row['path'])
        if path.suffix=='.py':compile(after,str(path),'exec')
        prepared[path]=after
    # Every input and output is checked before any code file changes.
    for path,raw in prepared.items():path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
    if tree(root)!=AFTER_TREE:raise ValueError('SQLITE_NAV_RECEIVER_TREE_MISMATCH')
    return {'policy':'SM-SQLITE-NAV-IMAGE-COMPOSITION-20261123-5','before_tree_sha256':BASE_TREE,
        'after_tree_sha256':AFTER_TREE,'replayed':False,'database_tables_added':0,'automatic_schema_migration':False,
        'source_marks_and_weight_preserved':True,'production_mutated':False,'official_ai_scoring_enabled':False}
