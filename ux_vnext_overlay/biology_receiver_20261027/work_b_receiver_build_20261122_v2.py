"""Build-only continuation of the existing source-delta materializer."""
from pathlib import Path,PurePosixPath
import hashlib
import json

BASE_TREE='056c8707eb48abccf12f66ddba799678c490e617c194f42910f44283e1d390ab'
AFTER_TREE='b8d3f04720891a65db3a45e9594f5a9f0d39b7c76a0223c3bf7c685064eb6737'
DELTA_SHA='380fc45264f715ee7297a0dbe114b00ffd318308543e01c1b153b6d003687319'
ALLOWED={'app.py','pending_saq_delivery_contract_v1.py','scored_saq_runtime_v1.py',
    'question_contract_engine.py','scoremax_integration_v1.py','scoremax_ph_bridge_v6611d.py',
    'ph_mastery_evidence.py','ph_withdrawal_scope_v1.py',
    'integration_contracts/v1_1_0/PH_SM_QUESTION_WITHDRAWAL_V1.schema.json','templates/result.html'}

def digest(raw):return hashlib.sha256(raw).hexdigest()
def tree(root):
    rows={p.relative_to(root).as_posix():digest(p.read_bytes()) for p in root.rglob('*')
        if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
    return digest(json.dumps(rows,sort_keys=True,separators=(',',':')).encode())

def apply(root):
    root=Path(root).resolve(strict=True)
    current=tree(root)
    if current==AFTER_TREE:return {'policy':'SM-WORK-B-RECEIVER-20261122-2','replayed':True,
        'after_tree_sha256':AFTER_TREE,'production_mutated':False,'official_ai_scoring_enabled':False}
    if current!=BASE_TREE:raise ValueError('WORK_B_EXACT_PRIOR_SCORED_RUNTIME_REQUIRED')
    raw=Path(__file__).with_name('work_b_receiver_delta_20261122_v2.json').read_bytes()
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
    return {'policy':'SM-WORK-B-RECEIVER-20261122-2','before_tree_sha256':BASE_TREE,
        'after_tree_sha256':AFTER_TREE,'replayed':False,'database_tables_added':0,
        'source_marks_and_weight_preserved':True,'production_mutated':False,'official_ai_scoring_enabled':False}
