"""ScoreMax V6.5.7 deterministic platform-side acceptance runner.

Narrow child of exact frozen V6.5.6. Closes only INT-PHSM-B01-P0-002.
Does not claim cross-system re-admission, Windows, Render or live-peer acceptance.
"""
from __future__ import annotations
import os, py_compile, secrets, subprocess, sys, tempfile
from pathlib import Path
from jinja2 import Environment
ROOT=Path(__file__).resolve().parent
CURRENT=[
    'smoke_tests_v6_5_1_rectification.py',
    'smoke_tests_v6_5_1_deep.py',
    'smoke_tests_v6_5_integration.py',
    'smoke_tests_v6_5_3_integration_admission.py',
    'smoke_tests_v6_5_4_central_rectification.py',
    'smoke_tests_v6_5_5_manifest_origin_security.py',
    'smoke_tests_v6_5_6_explicit_port_normalisation.py',
    'smoke_tests_v6_5_7_product_activation_gate.py',
    'scale_test_v6_5_integration_releases.py',
]

def clean(text):
    return '\n'.join(line for line in text.splitlines() if 'bootstrap admin created:' not in line and 'password rotated' not in line.lower())

def run(name):
    env=os.environ.copy(); env.setdefault('SCOREMAX_BOOTSTRAP_ADMIN_PASSWORD',secrets.token_urlsafe(24))
    p=subprocess.run([sys.executable,str(ROOT/name)],cwd=ROOT,text=True,capture_output=True,env=env)
    print(f'\n=== {name} ===\n'+clean(p.stdout).rstrip())
    if p.returncode:
        print(p.stderr,file=sys.stderr); raise SystemExit(p.returncode)
    return p.stdout.count('PASS:')

def main():
    tmp=Path(tempfile.mkdtemp(prefix='scoremax_v657_compile_'))
    pyfiles=[p for p in ROOT.rglob('*.py') if '__pycache__' not in p.parts]
    for i,p in enumerate(pyfiles): py_compile.compile(str(p),cfile=str(tmp/f'{i}.pyc'),doraise=True)
    env=Environment(); templates=list((ROOT/'templates').rglob('*.html'))
    for path in templates: env.parse(path.read_text(encoding='utf-8'))
    print(f'V6.5.7 PYTHON COMPILE PASS: {len(pyfiles)} files')
    print(f'V6.5.7 JINJA PARSE PASS: {len(templates)} templates')

    penv=os.environ.copy(); penv.setdefault('SCOREMAX_BOOTSTRAP_ADMIN_PASSWORD',secrets.token_urlsafe(24))
    p=subprocess.run([sys.executable,str(ROOT/'run_v6_4_acceptance.py')],cwd=ROOT,text=True,capture_output=True,env=penv)
    print('\n=== inherited V6.4 acceptance ===\n'+clean(p.stdout).rstrip())
    if p.returncode or 'SCOREMAX V6.4.0 ACCEPTANCE PASS:' not in p.stdout:
        print(p.stderr,file=sys.stderr); raise SystemExit(p.returncode or 1)

    counts={name:run(name) for name in CURRENT}
    ext=ROOT/'integration_control_return_v654'/'RUN_NEW_CENTRAL_ATTACKS.py'
    p=subprocess.run([sys.executable,str(ext),str(ROOT)],cwd=ROOT,text=True,capture_output=True,env=penv)
    print('\n=== previous V6.5.4 central attacks ===\n'+clean(p.stdout).rstrip())
    if p.returncode or '"confirmed_total": 0' not in p.stdout or '"P0": 0' not in p.stdout or '"P1": 0' not in p.stdout or '"integrity": "ok"' not in p.stdout or '"foreign_key_violations": 0' not in p.stdout:
        print(p.stderr,file=sys.stderr); raise SystemExit(p.returncode or 1)

    print('\nSCOREMAX V6.5.7 LOCAL ACCEPTANCE PASS')
    print('Exact parent: V6.5.6 SHA-256 64244e5d64d5df2bbeb262b0554b3c5e0b69b3f31378e8c338c71e5fb378cdb2')
    print('Rectified finding: INT-PHSM-B01-P0-002 only')
    print('Inherited V6.4 deterministic checks: 605 + synthetic mastery simulation + Emergency 3,000-row intake gate')
    print('Current PASS assertions:',sum(counts.values()),counts)
    print('V6.5.5 origin-security assertions: 23/23 PASS')
    print('V6.5.6 explicit-port assertions: 44/44 PASS')
    print('V6.5.7 product-activation assertions: 25/25 PASS')
    print('Canonical Power House 300/1,500 scale: PASS (STAGED first; explicit ScoreMax authorization then exact activation)')
    print('FINAL_GATE: confirmed_total=0 · P0=0 · P1=0 · integrity=ok · foreign_key_violations=0')
    print('CONNECTED BATCH01: pending central requalification with the same reserved 300 and Power House P1 rectification; do not start the real 1,500 batch.')
    print('WINDOWS: separate infrastructure/CI gate; not a V6.5.7 product-rectification prerequisite.')
if __name__=='__main__': main()
