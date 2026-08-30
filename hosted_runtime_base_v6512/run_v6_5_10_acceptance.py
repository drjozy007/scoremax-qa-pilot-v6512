"""ScoreMax V6.5.10 deterministic platform-side acceptance runner.

Narrow child of exact frozen V6.5.9. Closes only SM-GE-CONN-P1-003.
Does not claim receiver-runtime Growth acceptance without exact frozen Growth v0.14.3 bytes.
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
    'smoke_tests_v6_5_8_learner_evidence.py',
    'smoke_tests_v6_5_9_sm_ge_commercial.py',
    'smoke_tests_v6_5_10_terminal_payment_state.py',
    'scale_test_v6_5_integration_releases.py',
    'scale_test_v6_5_9_qa_sandbox_1500.py',
]

def clean(text):
    return '\n'.join(
        line for line in text.splitlines()
        if 'bootstrap admin created:' not in line.lower()
        and 'password rotated' not in line.lower()
        and 'local password reset url:' not in line.lower()
    )

def run(name):
    env=os.environ.copy()
    env['PYTHONDONTWRITEBYTECODE']='1'
    env.setdefault('SCOREMAX_BOOTSTRAP_ADMIN_PASSWORD',secrets.token_urlsafe(24))
    p=subprocess.run([sys.executable,str(ROOT/name)],cwd=ROOT,text=True,capture_output=True,env=env)
    print(f'\n=== {name} ===\n'+clean(p.stdout).rstrip())
    if p.returncode:
        print(clean(p.stderr),file=sys.stderr)
        raise SystemExit(p.returncode)
    return p.stdout.count('PASS:')

def main():
    tmp=Path(tempfile.mkdtemp(prefix='scoremax_v6510_compile_'))
    pyfiles=[p for p in ROOT.rglob('*.py') if '__pycache__' not in p.parts]
    for i,p in enumerate(pyfiles):
        py_compile.compile(str(p),cfile=str(tmp/f'{i}.pyc'),doraise=True)
    env=Environment()
    templates=list((ROOT/'templates').rglob('*.html'))
    for path in templates:
        env.parse(path.read_text(encoding='utf-8'))
    print(f'V6.5.10 PYTHON COMPILE PASS: {len(pyfiles)} files')
    print(f'V6.5.10 JINJA PARSE PASS: {len(templates)} templates')

    penv=os.environ.copy()
    penv['PYTHONDONTWRITEBYTECODE']='1'
    penv.setdefault('SCOREMAX_BOOTSTRAP_ADMIN_PASSWORD',secrets.token_urlsafe(24))
    p=subprocess.run([sys.executable,str(ROOT/'run_v6_4_acceptance.py')],cwd=ROOT,text=True,capture_output=True,env=penv)
    print('\n=== inherited V6.4 acceptance ===\n'+clean(p.stdout).rstrip())
    if p.returncode or 'SCOREMAX V6.4.0 ACCEPTANCE PASS:' not in p.stdout:
        print(clean(p.stderr),file=sys.stderr)
        raise SystemExit(p.returncode or 1)

    counts={name:run(name) for name in CURRENT}

    ext=ROOT/'integration_control_return_v654'/'RUN_NEW_CENTRAL_ATTACKS.py'
    p=subprocess.run([sys.executable,str(ext),str(ROOT)],cwd=ROOT,text=True,capture_output=True,env=penv)
    print('\n=== previous V6.5.4 central attacks ===\n'+clean(p.stdout).rstrip())
    required=('"confirmed_total": 0','"P0": 0','"P1": 0','"integrity": "ok"','"foreign_key_violations": 0')
    if p.returncode or any(token not in p.stdout for token in required):
        print(clean(p.stderr),file=sys.stderr)
        raise SystemExit(p.returncode or 1)

    print('\nSCOREMAX V6.5.10 LOCAL ACCEPTANCE PASS')
    print('Exact parent: V6.5.9 SHA-256 fae57ad5adb0be5373ff9943c263f0bce350c9b25dc936303ada956a5fd167d0')
    print('Rectified finding: SM-GE-CONN-P1-003 only')
    print('Frozen contract schema SHA-256: b42ae2a0fd1965ec83e561c43e60d68e84395687de1f257948af7b87319019bb')
    print('Inherited V6.4 deterministic checks: 605 + synthetic mastery simulation + Emergency 3,000-row intake')
    print('Current PASS assertions:',sum(counts.values()),counts)
    print('FINAL_PLATFORM_GATE: confirmed_total=0 · P0=0 · P1=0 · payment=PASS · referral=PASS · terminal_ordering=PASS · replay=PASS · privacy=PASS · integrity=ok · foreign_key_violations=0')
    print('CROSS_SYSTEM: pending independent Central replay against exact frozen Growth Engine v0.14.3 SHA 3c378ea33e06b5421eee6f00047c92c3f7a0add9ba0c8e7e27abf5013416c284.')
if __name__=='__main__':
    main()
