"""Evaluate all retained HTTP outcomes against the existing launch target."""
import argparse,json
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('--require-levels',default='1,10,50');a=p.parse_args()
m=json.loads((a.directory/'execution_manifest.json').read_text());levels={int(n) for n in a.require_levels.split(',')};checks=[]
for trial in m['trials']:
 d=json.loads(Path(trial['result']).read_text())
 assert d['protected_rows_unchanged_after_warmup'] and trial['returncode']==0
 assert {c['level'] for c in d['conditions']}==levels
 for c in d['conditions']:
  n=c['level'];s=c['successful_nav_latency'];passed=c['errors']==0 and not c['timeout_censoring'] and s['count']>=200 and s['p95_ms']<1500
  checks.append({'route':trial['route'],'level':n,'p95_ms':s['p95_ms'],'requests':s['count'],'errors':c['errors'],'passed':passed})
assert len({t['route'] for t in m['trials']})==4,'ALL_FOUR_NATIVE_ROUTES_REQUIRED'
report={'status':'PASSED' if all(c['passed'] for c in checks) else 'FAILED','checks':checks,'fixture':m['fixture'],'render_capacity_acceptance':'PENDING','production_actions':False}
(a.directory/'capacity_gate.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
assert report['status']=='PASSED','EXISTING_P95_1500MS_LAUNCH_CAPACITY_GATE_FAILED'
