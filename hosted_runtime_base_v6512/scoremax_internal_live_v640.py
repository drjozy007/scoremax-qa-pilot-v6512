"""Private/local ScoreMax V6.4.0 internal-live launcher.

Creates a persistent local database and secret under internal_live_data/ and starts
ScoreMax on localhost. This is intentionally not a public Internet deployment script.
"""
from __future__ import annotations
import os, secrets
from pathlib import Path

BASE=Path(__file__).resolve().parent
DATA=BASE/'internal_live_data'; DATA.mkdir(exist_ok=True)
secret_file=DATA/'session_secret_v640.txt'
if secret_file.exists():
    secret=secret_file.read_text().strip()
else:
    secret=secrets.token_urlsafe(48); secret_file.write_text(secret)

os.environ.setdefault('SCOREMAX_ENV','local')
os.environ.setdefault('SCOREMAX_DB',str(DATA/'scoremax_v6_4_0_internal_live.db'))
os.environ.setdefault('SCOREMAX_SECRET',secret)
os.environ.setdefault('SCOREMAX_UNIVERSAL_MASTERY','1')
os.environ.setdefault('SCOREMAX_HOST','127.0.0.1')
os.environ.setdefault('SCOREMAX_PORT','5000')
os.environ.setdefault('SCOREMAX_ENFORCE_PAYWALL','0')
os.environ.setdefault('SCOREMAX_INTERNAL_FULL_ACCESS','1')

import app

if __name__=='__main__':
    app.init()
    print('\nScoreMax V6.4.0 LIVE PILOT UX & OPERATIONS — INTERNAL LIVE')
    print('URL: http://127.0.0.1:%s' % os.environ['SCOREMAX_PORT'])
    print('Database:', os.environ['SCOREMAX_DB'])
    print('Universal mastery: PILOT/SHADOW alongside legacy mastery until governed mappings arrive')
    print('Academic reviewer workflow: Power House (not ScoreMax forward dependency)')
    print('Emergency Direct Intake: available to admin, capped at 3,000 rows, Draft/inactive by default\n')
    app.app.run(host=os.environ['SCOREMAX_HOST'],port=int(os.environ['SCOREMAX_PORT']),debug=False)
