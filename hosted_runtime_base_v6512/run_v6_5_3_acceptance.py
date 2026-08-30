"""ScoreMax V6.5.3 full local deterministic acceptance runner.

This is a platform-side, network-independent qualification. It does not claim Windows,
Render, live counterpart, browser/accessibility, SMTP, or founder acceptance.
"""
from __future__ import annotations
import py_compile, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
CURRENT=[
    'smoke_tests_v6_5_1_rectification.py',
    'smoke_tests_v6_5_1_deep.py',
    'smoke_tests_v6_5_integration.py',
    'smoke_tests_v6_5_3_integration_admission.py',
    'scale_test_v6_5_integration_releases.py',
]
COMPILE=['app.py','scoremax_integration_v1.py','scoremax_integration_dispatch_v1.py','scoremax_internal_live_v653.py','scoremax_internal_live_backup_v653.py']

def run(name):
    p=subprocess.run([sys.executable,str(ROOT/name)],cwd=ROOT,text=True,capture_output=True)
    print(f'\n=== {name} ===\n'+p.stdout.rstrip())
    if p.returncode:
        print(p.stderr,file=sys.stderr); raise SystemExit(p.returncode)
    return p.stdout.count('PASS:')

def main():
    for name in COMPILE: py_compile.compile(str(ROOT/name),doraise=True)
    print(f'V6.5.3 PYTHON COMPILE PASS: {len(COMPILE)} files')
    p=subprocess.run([sys.executable,str(ROOT/'run_v6_4_acceptance.py')],cwd=ROOT,text=True,capture_output=True)
    print('\n=== inherited V6.4 acceptance ===\n'+p.stdout.rstrip())
    if p.returncode:
        print(p.stderr,file=sys.stderr); raise SystemExit(p.returncode)
    if 'SCOREMAX V6.4.0 ACCEPTANCE PASS:' not in p.stdout:
        raise SystemExit('Inherited V6.4 acceptance did not emit its completion marker.')
    counts={name:run(name) for name in CURRENT}
    print('\nSCOREMAX V6.5.3 LOCAL ACCEPTANCE PASS')
    print('Inherited V6.4 deterministic checks: 605 + synthetic mastery simulation + Emergency 3,000-row intake gate')
    print('Current suite PASS assertions:',sum(counts.values()),counts)
    print('Canonical Power House 300/1,500 scale: PASS')
    print('STATUS: PLATFORM_SIDE_INTEGRATION_RECTIFIED_CANDIDATE_PENDING_CROSS_SYSTEM_QUALIFICATION')
    print('LIVE/CROSS-SYSTEM GATES REMAIN SEPARATE: Windows, Render/HTTPS/secrets, real Power House/Growth peers, real production corpus, browser/accessibility, SMTP, founder acceptance.')
if __name__=='__main__': main()
