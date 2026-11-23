"""Build-only continuation of the existing source-delta materializer."""
from pathlib import Path,PurePosixPath
import hashlib
import json

BASE_TREE='723ebb01fec680db2e88c9159deeac74b941cf4be8e5ab7d95b6691a3afb5bff'
AFTER_TREE='7c45b375d86c85b90e60467a98121a7d3d4ab15164228f5ac3a42c1e5e1df7f9'
DELTA_SHA='f9638530f1df6913643f2d4ee549574d2ecd98e538c21a69c53fdd1a4c0ef1fc'
ALLOWED={'scoremax_production.py', 'ux_student_batch.py', 'navigation_request_connections_v1.py', 'app.py', 'frozen_context_decode_v4.py', 'commercial_access_engine.py', 'navigation_template_compile_v1.py', 'ph_mastery_evidence.py', 'sqlite_mutation_engine.py', 'ux_content_reviewer.py', 'ux_staging_routes.py', 'ux_catalogue_browser.py', 'question_contract_engine.py', 'navigation_display_reads_v5.py', 'navigation_display_inventory_v3.py'}

def digest(raw):return hashlib.sha256(raw).hexdigest()
def tree(root):
    rows={p.relative_to(root).as_posix():digest(p.read_bytes()) for p in root.rglob('*')
        if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
    return digest(json.dumps(rows,sort_keys=True,separators=(',',':')).encode())

def apply(root):
    root=Path(root).resolve(strict=True)
    current=tree(root)
    if current==AFTER_TREE:return {'policy':'SM-SQLITE-NAV-NATIVE-MENU-CARD-BATCH-20261123-9','replayed':True,
        'after_tree_sha256':AFTER_TREE,'production_mutated':False,'official_ai_scoring_enabled':False}
    if current!=BASE_TREE:raise ValueError('SQLITE_NAV_EXACT_PRIOR_PENDING_RECEIVER_RUNTIME_REQUIRED')
    raw=Path(__file__).with_name('sqlite_navigation_delta_20261123_v9.json').read_bytes()
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
    return {'policy':'SM-SQLITE-NAV-NATIVE-MENU-CARD-BATCH-20261123-9','before_tree_sha256':BASE_TREE,
        'after_tree_sha256':AFTER_TREE,'replayed':False,'database_tables_added':0,'automatic_schema_migration':False,
        'source_marks_and_weight_preserved':True,'production_mutated':False,'official_ai_scoring_enabled':False}
