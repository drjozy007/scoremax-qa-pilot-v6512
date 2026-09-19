#!/usr/bin/env python3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/"scoremax_runtime_v669b"
terms=["def _activate_release","def activate_release","integration_ph_release_question_membership"]
for p in sorted(RUNTIME.rglob("*.py")):
    s=p.read_text(encoding="utf-8",errors="replace")
    for t in terms:
        start=0
        while True:
            i=s.find(t,start)
            if i<0: break
            print("SCOREMAX_ACTIVATION_SOURCE",p.relative_to(ROOT).as_posix(),t,flush=True)
            print(s[max(0,i-300):min(len(s),i+5000)],flush=True)
            start=i+len(t)
