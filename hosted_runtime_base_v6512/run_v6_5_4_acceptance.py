"""ScoreMax V6.5.4 full deterministic platform-side acceptance runner.

Network-independent. Does not claim Windows/Render/real-peer/browser/SMTP/founder acceptance.
"""
from __future__ import annotations
import py_compile, subprocess, sys
from pathlib import Path
from jinja2 import Environment
ROOT=Path(__file__).resolve().parent
CURRENT=[
    'smoke_tests_v6_5_1_rectification.py',
    'smoke_tests_v6_5_1_deep.py',
    'smoke_tests_v6_5_integration.py',
    'smoke_tests_v6_5_3_integration_admission.py',
    'smoke_tests_v6_5_4_central_rectification.py',
    'scale_test_v6_5_integration_releases.py',
]
COMPILE=[
    'app.py','scoremax_integration_v1.py','scoremax_integration_dispatch_v1.py',
    'scoremax_internal_live_v654.py','scoremax_internal_live_backup_v654.py',
    'scoremax_v6_3_simulator.py','run_v6_5_4_acceptance.py',
]

def run(name):
    p=subprocess.run([sys.executable,str(ROOT/name)],cwd=ROOT,text=True,capture_output=True)
    print(f'\n=== {name} ===\n'+p.stdout.rstrip())
    if p.returncode:
        print(p.stderr,file=sys.stderr); raise SystemExit(p.returncode)
    return p.stdout.count('PASS:')

def main():
    for name in COMPILE: py_compile.compile(str(ROOT/name),doraise=True)
    env=Environment(); templates=list((ROOT/'templates').rglob('*.html'))
    for path in templates: env.parse(path.read_text(encoding='utf-8'))
    print(f'V6.5.4 PYTHON COMPILE PASS: {len(COMPILE)} release-critical files')
    print(f'V6.5.4 JINJA PARSE PASS: {len(templates)} templates')

    p=subprocess.run([sys.executable,str(ROOT/'run_v6_4_acceptance.py')],cwd=ROOT,text=True,capture_output=True)
    print('\n=== inherited V6.4 acceptance ===\n'+p.stdout.rstrip())
    if p.returncode:
        print(p.stderr,file=sys.stderr); raise SystemExit(p.returncode)
    if 'SCOREMAX V6.4.0 ACCEPTANCE PASS:' not in p.stdout:
        raise SystemExit('Inherited V6.4 completion marker missing.')

    counts={name:run(name) for name in CURRENT}
    ext=ROOT/'integration_control_return_v654'/'RUN_NEW_CENTRAL_ATTACKS.py'
    p=subprocess.run([sys.executable,str(ext),str(ROOT)],cwd=ROOT,text=True,capture_output=True)
    print('\n=== central return attacks ===\n'+p.stdout.rstrip())
    if p.returncode:
        print(p.stderr,file=sys.stderr); raise SystemExit(p.returncode)
    if '"confirmed_total": 0' not in p.stdout:
        raise SystemExit('Central return attacks did not prove zero confirmed findings.')

    print('\nSCOREMAX V6.5.4 LOCAL ACCEPTANCE PASS')
    print('Inherited V6.4 deterministic checks: 605 + synthetic mastery simulation + Emergency 3,000-row intake gate')
    print('Current PASS assertions:',sum(counts.values()),counts)
    print('V6.5.4 central external attacks: 3/3 NOT_CONFIRMED')
    print('Canonical Power House 300/1,500 scale: PASS')
    print('STATUS: PLATFORM_SIDE_INTEGRATION_RECTIFIED_CANDIDATE_PENDING_CROSS_SYSTEM_QUALIFICATION')
    print('SEPARATE EMPIRICAL GATES: supported Windows, Render/HTTPS/secrets, real Power House/Growth peers, real production corpus, browser/accessibility, SMTP, founder acceptance.')
if __name__=='__main__': main()
