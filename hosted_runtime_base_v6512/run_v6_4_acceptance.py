"""ScoreMax V6.4.0 Live Pilot UX & Operations acceptance runner.

This runner qualifies the deterministic software delta in a restricted build environment.
Actual hosted-domain, browser/accessibility, SMTP and real Power House release acceptance remain
separate production-reality gates and are never inferred from this runner.
"""
from __future__ import annotations
import py_compile, subprocess, sys
from concurrent.futures import ThreadPoolExecutor, as_completed
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
V64=['smoke_tests_v6_4.py']
COMPILE=['app.py','universal_mastery_engine.py','student_experience_engine.py','commercial_access_engine.py','blueprint_engine.py',
         'daily_spark_engine.py','mastery_lab_engine.py','scoremax_internal_live_v640.py','scoremax_internal_live_backup_v640.py',
         'scoremax_production.py','scale_test_v6_4_emergency_3000.py']

def run(name):
    p=subprocess.run([sys.executable,str(ROOT/name)],cwd=ROOT,text=True,capture_output=True)
    print('\n===',name,'===')
    print(p.stdout.rstrip())
    if p.returncode:
        print(p.stderr,file=sys.stderr); raise SystemExit(p.returncode)
    return p.stdout.count('PASS:')

def run_cmd(args,label):
    p=subprocess.run(args,cwd=ROOT,text=True,capture_output=True)
    print(f'\n=== {label} ===\n'+p.stdout.rstrip())
    if p.returncode:
        print(p.stderr,file=sys.stderr); raise SystemExit(p.returncode)
    return p

def main():
    for name in COMPILE: py_compile.compile(str(ROOT/name),doraise=True)
    env=Environment(); templates=list((ROOT/'templates').rglob('*.html'))
    for path in templates: env.parse(path.read_text(encoding='utf-8'))
    print(f'PYTHON COMPILE PASS: {len(COMPILE)} files')
    print(f'JINJA PARSE PASS: {len(templates)} templates')

    # The suites use disposable independent databases, so run them in parallel to keep
    # founder/Windows acceptance fast without weakening any individual assertion.
    groups={'inherited':LEGACY,'v63':V63,'ux':UX,'chapter':CHAPTER,'v64':V64}
    ordered=[x for g in groups.values() for x in g]
    outputs={}; counts={}
    def run_capture(name):
        p=subprocess.run([sys.executable,str(ROOT/name)],cwd=ROOT,text=True,capture_output=True)
        return name,p.returncode,p.stdout,p.stderr,p.stdout.count('PASS:')
    with ThreadPoolExecutor(max_workers=min(6,len(ordered))) as pool:
        futures=[pool.submit(run_capture,name) for name in ordered]
        for fut in as_completed(futures):
            name,rc,out,err,count=fut.result(); outputs[name]=(rc,out,err); counts[name]=count
    for name in ordered:
        rc,out,err=outputs[name]
        print('\n===',name,'==='); print(out.rstrip())
        if rc:
            print(err,file=sys.stderr); raise SystemExit(rc)
    inherited=sum(counts[x] for x in LEGACY); v63=sum(counts[x] for x in V63); ux=sum(counts[x] for x in UX); chapter=sum(counts[x] for x in CHAPTER); v64=sum(counts[x] for x in V64)

    run_cmd([sys.executable,str(ROOT/'scoremax_v6_3_simulator.py'),'--learners','1000','--fuzz','10000',
             '--output',str(ROOT/'V6_4_0_SIMULATION_RESULTS_QUICK.json')],'synthetic mastery simulation')
    run_cmd([sys.executable,str(ROOT/'scale_test_v6_4_emergency_3000.py')],'3,000-row Emergency Direct Intake scale gate')

    total=inherited+v63+ux+chapter+v64
    print(f'\nSCOREMAX V6.4.0 ACCEPTANCE PASS: {inherited} inherited + {v63} V6.3 + {ux} UX V2 + {chapter} chapter identity + {v64} V6.4 = {total} deterministic checks + synthetic mastery simulation + 3,000-row end-to-end intake scale gate.')
    print('LIVE GATES STILL PENDING: domain/HTTPS/production host, real browser/accessibility, SMTP, real approved Power House chapter bridge, founder live acceptance.')

if __name__=='__main__': main()
