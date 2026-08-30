"""ScoreMax V6.3.2 Chapter Identity acceptance runner."""
from __future__ import annotations
import py_compile, subprocess, sys
from pathlib import Path
from jinja2 import Environment
ROOT=Path(__file__).resolve().parent
LEGACY=[
'smoke_tests_v5_5.py','smoke_tests_v6.py','smoke_tests_v6_1.py','smoke_tests_v6_2.py','smoke_tests_v6_2_1.py',
'smoke_tests_v6_2_2.py','smoke_tests_v6_2_3.py','smoke_tests_v6_2_4.py','smoke_tests_v6_2_5.py','smoke_tests_v6_2_6.py',
'smoke_tests_v6_2_7.py','smoke_tests_v6_2_7_1.py','smoke_tests_v6_2_7_2.py','smoke_tests_v6_2_8.py','smoke_tests_v6_2_8_1.py']
V63=['smoke_tests_v6_3.py','smoke_tests_v6_3_app.py']
UX=['smoke_tests_v6_3_1_ux.py']
CHAPTER=['smoke_tests_v6_3_2_chapter_identity.py']
COMPILE=['app.py','universal_mastery_engine.py','student_experience_engine.py','commercial_access_engine.py','blueprint_engine.py','daily_spark_engine.py','mastery_lab_engine.py']

def run(name):
    p=subprocess.run([sys.executable,str(ROOT/name)],cwd=ROOT,text=True,capture_output=True)
    print('\n===',name,'===')
    print(p.stdout.rstrip())
    if p.returncode:
        print(p.stderr,file=sys.stderr); raise SystemExit(p.returncode)
    return p.stdout.count('PASS:')

def main():
    for name in COMPILE: py_compile.compile(str(ROOT/name),doraise=True)
    env=Environment(); templates=list((ROOT/'templates').rglob('*.html'))
    for path in templates: env.parse(path.read_text())
    print(f'PYTHON COMPILE PASS: {len(COMPILE)} files')
    print(f'JINJA PARSE PASS: {len(templates)} templates')
    inherited=sum(run(x) for x in LEGACY)
    v63=sum(run(x) for x in V63)
    ux=sum(run(x) for x in UX)
    chapter=sum(run(x) for x in CHAPTER)
    p=subprocess.run([sys.executable,str(ROOT/'scoremax_v6_3_simulator.py'),'--learners','1000','--fuzz','10000','--output',str(ROOT/'V6_3_2_SIMULATION_RESULTS_QUICK.json')],cwd=ROOT,text=True,capture_output=True)
    print('\n=== synthetic simulation ===\n'+p.stdout.rstrip())
    if p.returncode:
        print(p.stderr,file=sys.stderr); raise SystemExit(p.returncode)
    total=inherited+v63+ux+chapter
    print(f'\nSCOREMAX V6.3.2 ACCEPTANCE PASS: {inherited} inherited + {v63} V6.3 + {ux} UX V2 + {chapter} chapter identity = {total} deterministic checks + synthetic simulation.')
if __name__=='__main__': main()
