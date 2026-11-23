import json,sys
from pathlib import Path
p=Path(sys.argv[1]);r=json.loads(p.read_text());m=json.loads(p.with_name(p.stem+'_mixed_actions.json').read_text());assert not m['writer_errors'];proofs=[a for a in m['actions'] if 'native_writer_result' in a];assert len(proofs)==1 and proofs[0]['preexisting_protected_tables_preserved']==16
for c in r['conditions']:
 assert c['errors']==0 and not c['timeout_censoring'] and c['successful_nav_latency']['count']>=400
 assert c['successful_nav_latency']['p95_ms']<1500,'MIXED_NAVIGATION_P95_1500MS_FAILED'
assert len([a for a in m['actions'] if 'path' in a])==6
print(json.dumps({'status':'PASSED','native_actual_submit_release_stop_and_backup':True,'native_peer_ACK_under_load':'PENDING_SEPARATE_CURRENT_PH_FIXTURE','real_bank_render_mobile':'PENDING','production_actions':False}))
