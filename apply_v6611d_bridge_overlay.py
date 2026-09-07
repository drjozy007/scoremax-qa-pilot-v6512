from __future__ import annotations

import hashlib
import json
import shutil
import sys
from pathlib import Path

PARENT_TREE_SHA256='0d2d399dcb6a23591a00b05d827a00804094cc17f94a676494b285eca4c79e5a'
MARKER='SM-PH-BRIDGE-V6611D-1'
ROOT=Path(sys.argv[1] if len(sys.argv)>1 else 'scoremax_runtime_v669b').resolve()
BASE=Path(__file__).resolve().parent
SRC=BASE/'v6611d_bridge'
PARENT_PATHS_FILE=BASE/'qualification/v6610f_runtime_paths.json'
ADDED_11C={
    'account_security_engine.py',
    'production_startup_engine.py',
    'simple_onboarding_engine.py',
    'sqlite_mutation_engine.py',
}


def sha256_file(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as fh:
        for block in iter(lambda: fh.read(1024*1024),b''):
            h.update(block)
    return h.hexdigest()


def qualified_parent_paths() -> set[str]:
    paths=set(json.loads(PARENT_PATHS_FILE.read_text(encoding='utf-8')))
    paths.discard('README_SCOREMAX_V6_6_9B.md')
    paths.discard('V6_6_9B_PACKAGE_MANIFEST.json')
    paths.add('production_content_seed_policy.py')
    paths.update(ADDED_11C)
    return paths


def qualified_digest(root: Path, paths: set[str]) -> str:
    h=hashlib.sha256()
    for rel in sorted(paths):
        path=root/rel
        if not path.is_file():
            raise SystemExit(f'V6611D_PARENT_PATH_MISSING:{rel}')
        h.update(f'{rel}\0{sha256_file(path)}\0{path.stat().st_size}\n'.encode())
    return h.hexdigest()


def full_runtime_digest(root: Path) -> str:
    return qualified_digest(root,{p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()})


def replace_once(path: Path, old: str, new: str):
    text=path.read_text(encoding='utf-8')
    n=text.count(old)
    if n!=1:
        raise SystemExit(f'V6611D_PATCH_ANCHOR_MISMATCH path={path.name} count={n} anchor={old[:100]!r}')
    path.write_text(text.replace(old,new,1),encoding='utf-8')


if not ROOT.exists():
    raise SystemExit('V6611D_RUNTIME_ROOT_MISSING')
parent_paths=qualified_parent_paths()
actual_paths={p.relative_to(ROOT).as_posix() for p in ROOT.rglob('*') if p.is_file()}
if actual_paths!=parent_paths:
    missing=sorted(parent_paths-actual_paths); extra=sorted(actual_paths-parent_paths)
    raise SystemExit(f'V6611D_PARENT_PATH_SET_MISMATCH missing={missing[:8]} extra={extra[:8]}')
actual_parent=qualified_digest(ROOT,parent_paths)
if actual_parent!=PARENT_TREE_SHA256:
    raise SystemExit(f'V6611D_PARENT_TREE_SHA_MISMATCH expected={PARENT_TREE_SHA256} actual={actual_parent}')

app=ROOT/'app.py'
integration=ROOT/'scoremax_integration_v1.py'
if "SCOREMAX_RELEASE_VERSION='6.6.11C'" not in app.read_text(encoding='utf-8'):
    raise SystemExit('V6611D_PARENT_RELEASE_MARKER_MISSING')
if "SCOREMAX_INTEGRATION_RELEASE='6.6.11C'" not in integration.read_text(encoding='utf-8'):
    raise SystemExit('V6611D_PARENT_INTEGRATION_MARKER_MISSING')

shutil.copy2(SRC/'scoremax_ph_bridge_v6611d.py',ROOT/'scoremax_ph_bridge_v6611d.py')
contract_dir=ROOT/'integration_contracts'; contract_dir.mkdir(exist_ok=True)
for source in sorted((SRC/'contracts').glob('*.schema.json')):
    shutil.copy2(source,contract_dir/source.name)

receipt_path=contract_dir/'INTEGRATION_RECEIPT_V1.schema.json'
receipt=json.loads(receipt_path.read_text(encoding='utf-8'))
enum=receipt['properties']['contract_name']['enum']
for name in ('SM_PH_CONTENT_DELIVERY_ACK_V1','SM_PH_CONTENT_INCIDENT_V1','PH_SM_QUESTION_WITHDRAWAL_V1','SM_PH_QUESTION_WITHDRAWAL_ACK_V1'):
    if name not in enum: enum.append(name)
receipt['properties']['contract_name']['enum']=sorted(enum)
receipt_path.write_text(json.dumps(receipt,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')

replace_once(app,"import scoremax_integration_v1 as integration_v1\n","import scoremax_integration_v1 as integration_v1\nimport scoremax_ph_bridge_v6611d as ph_bridge_v6611d\nph_bridge_v6611d.install(integration_v1)\n")
replace_once(app,"    integration_v1.init_schema(c)\n    migrate_v6_6_7a_family_absorption(c)","    integration_v1.init_schema(c)\n    ph_bridge_v6611d.init_schema(c)\n    migrate_v6_6_7a_family_absorption(c)")
replace_once(app,'question=c.execute("SELECT id,question_id,subject,chapter,question FROM questions WHERE id=?",(question_id,)).fetchone()',
'''question=c.execute("""SELECT id,question_id,subject,chapter,question,ph_projection_owner,ph_question_id,ph_question_version_id,ph_question_checksum_sha256,ph_release_id,ph_release_version,ph_release_checksum_sha256,ph_market_id,ph_programme_id,ph_subject_id,ph_chapter_id FROM questions WHERE id=?""",(question_id,)).fetchone()''')
replace_once(app,
"        pilot_record_event(c,'PILOT_FEEDBACK_SUBMITTED','pilot_feedback',code,{'category':category,'routing_target':target,'severity':severity,'context':context},session['user_id']); c.commit(); c.close()",
"        if question:\n            ph_bridge_v6611d.queue_reported_question_incident(c,question,code,category,severity,description,context)\n        pilot_record_event(c,'PILOT_FEEDBACK_SUBMITTED','pilot_feedback',code,{'category':category,'routing_target':target,'severity':severity,'context':context},session['user_id']); c.commit(); c.close()")
route_anchor="@app.route('/api/integration/v1/power-house/assessment-blueprints',methods=['POST'])\ndef integration_power_house_assessment_blueprint():"
route_new="""@app.route('/api/integration/v1/power-house/question-withdrawals',methods=['POST'])
def integration_power_house_question_withdrawals():
    envelope,error=_integration_parse_verified('POWER_HOUSE','PH_SM_QUESTION_WITHDRAWAL_V1')
    if error: return error
    c=db()
    try:
        ph_bridge_v6611d.init_schema(c)
        receipt,status=ph_bridge_v6611d.admit_withdrawal_envelope(c,envelope,request.headers.get('X-Content-SHA256',''))
        return jsonify(receipt),status
    finally:
        c.close()


@app.route('/api/integration/v1/power-house/assessment-blueprints',methods=['POST'])
def integration_power_house_assessment_blueprint():"""
replace_once(app,route_anchor,route_new)
replace_once(app,"SCOREMAX_RELEASE_VERSION='6.6.11C'","SCOREMAX_RELEASE_VERSION='6.6.11D'")
replace_once(integration,"SCOREMAX_INTEGRATION_RELEASE='6.6.11C'","SCOREMAX_INTEGRATION_RELEASE='6.6.11D'")

marker={
  'marker':MARKER,
  'release':'6.6.11D',
  'parent_runtime_tree_sha256':PARENT_TREE_SHA256,
  'release_authority_changed':False,
  'cross_system_calls_on_learner_request':False,
}
(ROOT/'V6611D_PH_BRIDGE_MARKER.json').write_text(json.dumps(marker,sort_keys=True,indent=2)+'\n',encoding='utf-8')
final_sha=full_runtime_digest(ROOT)
print(f'V6611D_BRIDGE_OVERLAY_APPLIED marker={MARKER} parent_tree_sha256={PARENT_TREE_SHA256} runtime_tree_sha256={final_sha} release=6.6.11D')
