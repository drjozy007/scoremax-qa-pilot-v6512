#!/usr/bin/env python3
"""V6.5.4 return orchestrator for the newly discovered central findings.

Usage: python RUN_BEFORE_RETURN.py <V6.5.4-candidate.zip>

This orchestrator is intentionally narrow: it runs the new central attacks. The platform workstream must
also run every inherited/current ScoreMax suite listed in the return gates; do not use this file as a substitute
for the full acceptance runner.
"""
from pathlib import Path
import subprocess, sys
if len(sys.argv)!=2:
    raise SystemExit('Usage: python RUN_BEFORE_RETURN.py <candidate.zip>')
script=Path(__file__).with_name('RUN_NEW_CENTRAL_ATTACKS.py')
rc=subprocess.call([sys.executable,str(script),sys.argv[1]])
if rc:
    raise SystemExit(rc)
print('NEW CENTRAL ATTACKS: 0 confirmed. Now run all full/inherited/scale/migration/Windows/package gates before return.')
