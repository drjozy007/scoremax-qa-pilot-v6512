"""Private/local ScoreMax V6.5.5 integration admission-rectification internal-live launcher."""
from __future__ import annotations
import os, secrets
from pathlib import Path
BASE=Path(__file__).resolve().parent
DATA=BASE/'internal_live_data'; DATA.mkdir(exist_ok=True)
secret_file=DATA/'session_secret_v655.txt'
secret=secret_file.read_text().strip() if secret_file.exists() else secrets.token_urlsafe(48)
if not secret_file.exists(): secret_file.write_text(secret)
os.environ.setdefault('SCOREMAX_ENV','local')
os.environ.setdefault('SCOREMAX_DB',str(DATA/'scoremax_v6_5_5_internal_live.db'))
os.environ.setdefault('SCOREMAX_SECRET',secret)
os.environ.setdefault('SCOREMAX_UNIVERSAL_MASTERY','1')
os.environ.setdefault('SCOREMAX_HOST','127.0.0.1')
os.environ.setdefault('SCOREMAX_PORT','5000')
os.environ.setdefault('SCOREMAX_ENFORCE_PAYWALL','0')
os.environ.setdefault('SCOREMAX_INTERNAL_FULL_ACCESS','1')
import app
if __name__=='__main__':
    app.init()
    print('\nScoreMax V6.5.5 POWER HOUSE MANIFEST ORIGIN SECURITY RECTIFICATION — INTERNAL LIVE')
    print('URL: http://127.0.0.1:%s' % os.environ['SCOREMAX_PORT'])
    print('Database:',os.environ['SCOREMAX_DB'])
    print('Power House content/blueprints: governed contract v1.0 INLINE + v1.1 INLINE/MANIFEST_PULL/WITHDRAW adapters enabled')
    print('Growth Engine: asynchronous fair/leased product-referral event outbox enabled')
    print('Universal mastery: PILOT/SHADOW until governed version-aware mapping promotion is separately accepted')
    print('Academic reviewer workflow: Power House\n')
    app.app.run(host=os.environ['SCOREMAX_HOST'],port=int(os.environ['SCOREMAX_PORT']),debug=False)
