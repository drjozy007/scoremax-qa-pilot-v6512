from __future__ import annotations
from pathlib import Path

MARKER='SCOREMAX_INTEGRATION_ROUTE_AUDIT_V1'


def apply_integration_route_audit(root: Path) -> None:
    module=root/'ux_integration_route_audit_runtime.py'
    module.write_text('''from __future__ import annotations\nimport json,os\n\ndef run(app):\n    if str(os.environ.get("SCOREMAX_INTEGRATION_ROUTE_AUDIT","0")).strip().lower() not in {"1","true","yes","on"}:\n        print("SCOREMAX_INTEGRATION_ROUTE_AUDIT disabled=true",flush=True); return\n    rows=[]\n    for rule in app.url_map.iter_rules():\n        path=str(rule.rule or "")\n        endpoint=str(rule.endpoint or "")\n        hay=(path+" "+endpoint).lower()\n        if "integration" not in hay and "withdraw" not in hay and "power_house" not in hay and "powerhouse" not in hay:\n            continue\n        rows.append({"path":path,"endpoint":endpoint,"methods":sorted(m for m in (rule.methods or set()) if m not in {"HEAD","OPTIONS"})})\n    rows=sorted(rows,key=lambda x:(x["path"],x["endpoint"]))\n    print("SCOREMAX_INTEGRATION_ROUTE_AUDIT "+json.dumps({"count":len(rows),"routes":rows},sort_keys=True,separators=(",",":")),flush=True)\n''',encoding='utf-8')
    production=root/'scoremax_production.py'
    text=production.read_text(encoding='utf-8')
    anchor='application=scoremax.app'
    new='from ux_integration_route_audit_runtime import run as _run_integration_route_audit\n_run_integration_route_audit(scoremax.app)\napplication=scoremax.app'
    if '_run_integration_route_audit(scoremax.app)' not in text:
        idx=text.rfind(anchor)
        if idx<0: raise SystemExit('SCOREMAX_INTEGRATION_ROUTE_AUDIT_APPLICATION_ANCHOR_MISSING')
        text=text[:idx]+new+text[idx+len(anchor):]
        production.write_text(text,encoding='utf-8')
    print(f'{MARKER} PASS read_only=true env_gated=true route_metadata_only=true payloads=false credentials=false users=false',flush=True)
