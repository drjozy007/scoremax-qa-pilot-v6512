from __future__ import annotations

import json, sys
from pathlib import Path

MARKER='SM-PH-STAGED-WITHDRAWAL-V6611E-1'
RELEASE='6.6.11E'
ROOT=Path(sys.argv[1] if len(sys.argv)>1 else 'scoremax_runtime_v669b').resolve()

def replace_once(path:Path,old:str,new:str):
    text=path.read_text(encoding='utf-8')
    n=text.count(old)
    if n!=1:
        raise SystemExit(f'V6611E_PATCH_ANCHOR_MISMATCH path={path.name} count={n} anchor={old[:120]!r}')
    path.write_text(text.replace(old,new,1),encoding='utf-8')

app=ROOT/'app.py'
integration=ROOT/'scoremax_integration_v1.py'
bridge=ROOT/'scoremax_ph_bridge_v6611d.py'
if not all(p.is_file() for p in (app,integration,bridge)):
    raise SystemExit('V6611E_PARENT_RUNTIME_MISSING')
if "SCOREMAX_RELEASE_VERSION='6.6.11D'" not in app.read_text(encoding='utf-8'):
    raise SystemExit('V6611E_PARENT_APP_RELEASE_MISMATCH')
if "SCOREMAX_INTEGRATION_RELEASE='6.6.11D'" not in integration.read_text(encoding='utf-8'):
    raise SystemExit('V6611E_PARENT_INTEGRATION_RELEASE_MISMATCH')
if "RELEASE='6.6.11D'" not in bridge.read_text(encoding='utf-8'):
    raise SystemExit('V6611E_PARENT_BRIDGE_RELEASE_MISMATCH')

schema_old="""    CREATE TABLE IF NOT EXISTS ph_bridge_withdrawal_receipts_v6611d(
      id INTEGER PRIMARY KEY,
      export_public_id TEXT NOT NULL UNIQUE,
      population_sha256 TEXT NOT NULL,
      inbound_message_id TEXT NOT NULL,
      item_count INTEGER NOT NULL,
      ack_message_id TEXT NOT NULL DEFAULT '',
      receipt_sha256 TEXT NOT NULL,
      created_at TEXT NOT NULL
    );
"""
schema_new=schema_old+"""    CREATE TABLE IF NOT EXISTS ph_bridge_staged_withdrawal_exclusions_v6611e(
      id INTEGER PRIMARY KEY,
      release_id TEXT NOT NULL,
      release_version TEXT NOT NULL,
      question_id TEXT NOT NULL,
      question_version_id TEXT NOT NULL,
      question_checksum_sha256 TEXT NOT NULL,
      item_public_id TEXT NOT NULL,
      export_public_id TEXT NOT NULL,
      population_sha256 TEXT NOT NULL,
      withdrawal_queue_id TEXT NOT NULL DEFAULT '',
      hold_id TEXT NOT NULL DEFAULT '',
      defect_code TEXT NOT NULL DEFAULT '',
      reason TEXT NOT NULL DEFAULT '',
      item_sha256 TEXT NOT NULL,
      created_at TEXT NOT NULL,
      UNIQUE(release_id,release_version,question_id,question_version_id)
    );
    CREATE INDEX IF NOT EXISTS idx_ph_staged_withdrawal_exclusion_q_v6611e
      ON ph_bridge_staged_withdrawal_exclusions_v6611e(question_id,question_version_id,release_id,release_version);
"""
replace_once(bridge,schema_old,schema_new)

count_old="""    count=int(c.execute('SELECT COUNT(*) n FROM integration_ph_release_question_membership WHERE release_id=? AND release_version=?',(release_id,release_version)).fetchone()['n'] or 0)
"""
count_new="""    count=int(c.execute('''SELECT COUNT(*) n FROM integration_ph_release_question_membership m
      WHERE m.release_id=? AND m.release_version=?
        AND NOT EXISTS (
          SELECT 1 FROM ph_bridge_staged_withdrawal_exclusions_v6611e e
          WHERE e.release_id=m.release_id AND e.release_version=m.release_version
            AND e.question_id=m.question_id AND e.question_version_id=m.question_version_id
        )''',(release_id,release_version)).fetchone()['n'] or 0)
"""
replace_once(bridge,count_old,count_new)

withdraw_old='''def _withdraw_one(c, item):
    qid=str(item.get('question_public_id') or '').strip()
    if not qid:
        return {'item_public_id':str(item.get('item_public_id') or ''),'question_public_id':'','state':'NOT_PRESENT','historical_attempts_preserved':True}
    rows=c.execute("SELECT id,active,status FROM questions WHERE ph_projection_owner='POWER_HOUSE' AND ph_question_id=? ORDER BY id",(qid,)).fetchall()
    active=[r for r in rows if int(r['active'] or 0)==1]
    if not rows: state='NOT_PRESENT'
    elif not active: state='ALREADY_WITHDRAWN'
    else:
        ids=[int(r['id']) for r in active]
        marks=','.join('?' for _ in ids)
        c.execute(f"UPDATE questions SET active=0,status='Withdrawn' WHERE id IN ({marks})",ids)
        state='WITHDRAWN'
    return {
      'item_public_id':str(item.get('item_public_id') or ''),
      'question_public_id':qid,
      'state':state,
      'historical_attempts_preserved':True,
    }
'''
withdraw_new='''def _withdraw_one(c, item, export_public_id='', population_sha256=''):
    qid=str(item.get('question_public_id') or '').strip()
    if not qid:
        return {'item_public_id':str(item.get('item_public_id') or ''),'question_public_id':'','state':'NOT_PRESENT','historical_attempts_preserved':True}
    init_schema(c)
    rows=c.execute("SELECT id,active,status FROM questions WHERE ph_projection_owner='POWER_HOUSE' AND ph_question_id=? ORDER BY id",(qid,)).fetchall()
    active=[r for r in rows if int(r['active'] or 0)==1]
    if active:
        ids=[int(r['id']) for r in active]
        marks=','.join('?' for _ in ids)
        c.execute(f"UPDATE questions SET active=0,status='Withdrawn' WHERE id IN ({marks})",ids)

    # Staged releases have no learner rows yet. Bind the stop to exactly one stored question/version.
    staged=c.execute("""SELECT m.release_id,m.release_version,m.question_id,m.question_version_id,
                              v.question_checksum_sha256,r.local_status
                       FROM integration_ph_release_question_membership m
                       JOIN integration_ph_question_version_store v
                         ON v.question_id=m.question_id AND v.question_version_id=m.question_version_id
                       JOIN integration_ph_content_releases r
                         ON r.release_id=m.release_id AND r.release_version=m.release_version
                       WHERE m.question_id=? AND r.local_status='STAGED'
                       ORDER BY r.admitted_at,m.ordinal,m.id""",(qid,)).fetchall()
    fp=str(item.get('question_version_fingerprint') or '').strip()
    if fp:
        exact=[r for r in staged if fp in {
            str(r['question_version_id'] or ''),
            str(r['question_checksum_sha256'] or '').lower(),
            _sha_text(str(r['question_version_id'] or '')),
            _sha_text(str(r['question_checksum_sha256'] or '').lower()),
        }]
        if exact: staged=exact
    # Ambiguity is unsafe: do not create a staged exclusion unless there is one exact candidate.
    if len(staged)>1:
        return {'item_public_id':str(item.get('item_public_id') or ''),'question_public_id':qid,
                'state':'AMBIGUOUS_STAGED_IDENTITY','historical_attempts_preserved':True}
    staged_excluded=False
    if len(staged)==1:
        rv=staged[0]
        item_public_id=str(item.get('item_public_id') or '')
        item_sha=str(item.get('item_sha256') or '').lower()
        if not item_public_id or len(item_sha)!=64:
            return {'item_public_id':item_public_id,'question_public_id':qid,
                    'state':'INVALID_WITHDRAWAL_ITEM_IDENTITY','historical_attempts_preserved':True}
        c.execute("""INSERT OR IGNORE INTO ph_bridge_staged_withdrawal_exclusions_v6611e(
                     release_id,release_version,question_id,question_version_id,question_checksum_sha256,
                     item_public_id,export_public_id,population_sha256,withdrawal_queue_id,hold_id,
                     defect_code,reason,item_sha256,created_at)
                     VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  (str(rv['release_id']),str(rv['release_version']),qid,str(rv['question_version_id']),
                   str(rv['question_checksum_sha256']).lower(),item_public_id,str(export_public_id),
                   str(population_sha256).lower(),str(item.get('withdrawal_queue_id') or ''),
                   str(item.get('hold_id') or ''),str(item.get('defect_code') or ''),
                   str(item.get('reason') or '')[:4000],item_sha,_INTEGRATION.utcnow()))
        staged_excluded=True

    if active and staged_excluded: state='WITHDRAWN_AND_STAGED_EXCLUDED'
    elif active: state='WITHDRAWN'
    elif staged_excluded: state='STAGED_EXCLUDED'
    elif rows: state='ALREADY_WITHDRAWN'
    else: state='NOT_PRESENT'
    return {
      'item_public_id':str(item.get('item_public_id') or ''),
      'question_public_id':qid,
      'state':state,
      'historical_attempts_preserved':True,
    }
'''
replace_once(bridge,withdraw_old,withdraw_new)
replace_once(bridge,"    results=[_withdraw_one(c,item) for item in items]\n",
             "    results=[_withdraw_one(c,item,export_id,pop) for item in items]\n")

qvs_old="""    qvs=c.execute('''SELECT v.*,m.ordinal FROM integration_ph_release_question_membership m
      JOIN integration_ph_question_version_store v ON v.question_id=m.question_id AND v.question_version_id=m.question_version_id
      WHERE m.release_id=? AND m.release_version=? ORDER BY m.ordinal,m.id''',(release_id,release_version)).fetchall()
"""
qvs_new="""    qvs=c.execute('''SELECT v.*,m.ordinal FROM integration_ph_release_question_membership m
      JOIN integration_ph_question_version_store v ON v.question_id=m.question_id AND v.question_version_id=m.question_version_id
      WHERE m.release_id=? AND m.release_version=?
        AND NOT EXISTS (
          SELECT 1 FROM ph_bridge_staged_withdrawal_exclusions_v6611e e
          WHERE e.release_id=m.release_id AND e.release_version=m.release_version
            AND e.question_id=m.question_id AND e.question_version_id=m.question_version_id
        )
      ORDER BY m.ordinal,m.id''',(release_id,release_version)).fetchall()
"""
replace_once(integration,qvs_old,qvs_new)

replace_once(app,"SCOREMAX_RELEASE_VERSION='6.6.11D'","SCOREMAX_RELEASE_VERSION='6.6.11E'")
replace_once(integration,"SCOREMAX_INTEGRATION_RELEASE='6.6.11D'","SCOREMAX_INTEGRATION_RELEASE='6.6.11E'")
replace_once(bridge,"RELEASE='6.6.11D'","RELEASE='6.6.11E'")

marker={
  'marker':MARKER,
  'release':RELEASE,
  'parent_release':'6.6.11D',
  'immutable_membership_preserved':True,
  'staged_question_exclusion':True,
  'activation_filters_exclusions':True,
  'historical_attempts_preserved':True,
  'release_authority_changed':False,
  'cross_system_calls_on_learner_request':False,
}
(ROOT/'V6611E_STAGED_WITHDRAWAL_MARKER.json').write_text(json.dumps(marker,sort_keys=True,indent=2)+'\n',encoding='utf-8')
for p in (app,integration,bridge):
    compile(p.read_text(encoding='utf-8'),str(p),'exec')
print('V6611E_STAGED_WITHDRAWAL_OVERLAY_PASS immutable_membership=true staged_exclusion=true activation_filter=true historical_attempts_preserved=true release_authority=false',flush=True)
