"""Run ScoreMax V6.3 inherited + new acceptance checks."""
from __future__ import annotations
import subprocess, sys, re
from pathlib import Path
ROOT=Path(__file__).resolve().parent
LEGACY=[
'smoke_tests_v5_5.py','smoke_tests_v6.py','smoke_tests_v6_1.py','smoke_tests_v6_2.py','smoke_tests_v6_2_1.py',
'smoke_tests_v6_2_2.py','smoke_tests_v6_2_3.py','smoke_tests_v6_2_4.py','smoke_tests_v6_2_5.py','smoke_tests_v6_2_6.py',
'smoke_tests_v6_2_7.py','smoke_tests_v6_2_7_1.py','smoke_tests_v6_2_7_2.py','smoke_tests_v6_2_8.py','smoke_tests_v6_2_8_1.py']
NEW=['smoke_tests_v6_3.py','smoke_tests_v6_3_app.py']

def run(name):
    p=subprocess.run([sys.executable,str(ROOT/name)],cwd=ROOT,text=True,capture_output=True)
    print('\n===',name,'===')
    print(p.stdout.rstrip())
    if p.returncode:
        print(p.stderr,file=sys.stderr); raise SystemExit(p.returncode)
    return p.stdout

def main():
    inherited_checks=0
    new_checks=0
    for x in LEGACY:
        inherited_checks += run(x).count('PASS:')
    for x in NEW:
        new_checks += run(x).count('PASS:')
    # Fast routine simulation; the release package also ships the larger recorded result.
    p=subprocess.run([sys.executable,str(ROOT/'scoremax_v6_3_simulator.py'),'--learners','1000','--fuzz','10000','--output',str(ROOT/'V6_3_0_SIMULATION_RESULTS_QUICK.json')],cwd=ROOT,text=True,capture_output=True)
    print('\n=== synthetic simulation ===\n'+p.stdout.rstrip())
    if p.returncode:
        print(p.stderr,file=sys.stderr); raise SystemExit(p.returncode)
    print(f'\nSCOREMAX V6.3.0 ACCEPTANCE PASS: {inherited_checks} inherited + {new_checks} new deterministic checks + synthetic simulation.')
if __name__=='__main__': main()
