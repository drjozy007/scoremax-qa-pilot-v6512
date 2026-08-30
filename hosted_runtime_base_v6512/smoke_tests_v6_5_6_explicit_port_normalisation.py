"""ScoreMax V6.5.6 permanent regression for explicit-port origin normalization.

Narrow child of frozen V6.5.5. Proves explicit zero/invalid/out-of-range
ports cannot normalize into the trusted Power House HTTPS origin, including
redirect targets, while legitimate same-origin default/non-default ports
retain existing behavior. No external network is used.
"""
from __future__ import annotations
from release_compatibility import is_compatible_descendant
import os, sys, tempfile
from pathlib import Path

TMP=Path(tempfile.mkdtemp(prefix='scoremax_v656_port_'))
ROOT=Path(__file__).resolve().parent
TOKEN='V656-PH-BEARER-SECRET-MUST-NEVER-LEAK'
os.environ.update({
    'SCOREMAX_DB':str(TMP/'scoremax.db'),
    'SCOREMAX_SECRET':'V656-Port-Normalisation-Disposable-Secret',
    'SCOREMAX_ENV':'test','SCOREMAX_ENFORCE_PAYWALL':'0','SCOREMAX_INTERNAL_FULL_ACCESS':'1',
    'SCOREMAX_POWER_HOUSE_BASE_URL':'https://power-house.example.invalid',
    'SCOREMAX_TO_POWER_HOUSE_TOKEN':TOKEN,
    'SCOREMAX_TO_POWER_HOUSE_HMAC_SECRET':'v656-sm-ph-secret-long-enough-for-hmac',
    'POWER_HOUSE_TO_SCOREMAX_TOKEN':'v656-ph-token-long-enough',
    'POWER_HOUSE_TO_SCOREMAX_HMAC_SECRET':'v656-ph-secret-long-enough-for-hmac',
    'SCOREMAX_GROWTH_ENGINE_BASE_URL':'https://growth.example.invalid',
    'SCOREMAX_TO_GROWTH_ENGINE_TOKEN':'v656-growth-token-long-enough',
    'SCOREMAX_TO_GROWTH_ENGINE_HMAC_SECRET':'v656-growth-secret-long-enough-for-hmac',
})
sys.path.insert(0,str(ROOT))
from smoke_tests_v5_5 import install_framework_stubs
install_framework_stubs()
import app
import scoremax_integration_v1 as integ
app.init(); c=app.db(); integ.init_schema(c); c.commit()

N=0
def ok(name,cond):
    global N
    if not cond: raise AssertionError(name)
    N+=1; print('PASS:',name)

ok('release identity is V6.5.6',is_compatible_descendant(app.SCOREMAX_RELEASE_VERSION,'6.5.6') and is_compatible_descendant(integ.SCOREMAX_INTEGRATION_RELEASE,'6.5.6'))

# Direct package URLs: every malformed/zero/out-of-range port must fail BEFORE
# credential access and BEFORE opener/network construction.
orig_cred=integ._manifest_pull_credentials
orig_build=integ.urlrequest.build_opener
bad_direct=[
    (':0','https://power-house.example.invalid:0/pkg.zip'),
    (':00','https://power-house.example.invalid:00/pkg.zip'),
    (':000','https://power-house.example.invalid:000/pkg.zip'),
    ('non-numeric','https://power-house.example.invalid:abc/pkg.zip'),
    ('negative','https://power-house.example.invalid:-1/pkg.zip'),
    ('out-of-range','https://power-house.example.invalid:65536/pkg.zip'),
    ('very-out-of-range','https://power-house.example.invalid:999999/pkg.zip'),
]
for label,bad in bad_direct:
    calls={'cred':0,'open':0}
    def no_cred():
        calls['cred']+=1
        raise AssertionError('credential accessed before explicit-port validation')
    def no_open(*a,**k):
        calls['open']+=1
        raise AssertionError('opener/network constructed before explicit-port validation')
    integ._manifest_pull_credentials=no_cred
    integ.urlrequest.build_opener=no_open
    blocked=False; message=''
    try: integ._download_manifest_package(bad,timeout=1)
    except ValueError as exc: blocked=True; message=str(exc)
    finally:
        integ._manifest_pull_credentials=orig_cred
        integ.urlrequest.build_opener=orig_build
    ok('direct '+label+' port blocked',blocked)
    ok('direct '+label+' fails before credential/network',calls=={'cred':0,'open':0})
    ok('direct '+label+' rejection does not disclose bearer token',TOKEN not in message)

# Explicit :443 is semantically the same HTTPS origin when the configured base
# omits the default port. Validation succeeds before the normal credential/read path.
url,origin=integ._validate_power_house_package_url('https://power-house.example.invalid:443/pkg.zip')
ok('explicit :443 matches configured default HTTPS origin',origin==('https','power-house.example.invalid',443) and ':443/' in url)

# Redirect targets: the initial trusted request may already carry its credential,
# but a redirect to zero/invalid/out-of-range port must be rejected before urllib
# constructs/sends a redirected request. The error itself must not expose the token.
handler=integ._PowerHouseSameOriginRedirectHandler(integ._trusted_power_house_origin())
req=integ.urlrequest.Request('https://power-house.example.invalid/releases/a.zip',headers={'Authorization':'Bearer '+TOKEN},method='GET')
for label,bad in bad_direct:
    target=bad.replace('/pkg.zip','/redirected.zip')
    blocked=False; message=''
    try: handler.redirect_request(req,None,302,'Found',{},target)
    except ValueError as exc: blocked=True; message=str(exc)
    ok('redirect '+label+' port blocked before redirected request',blocked)
    ok('redirect '+label+' rejection does not disclose bearer token',TOKEN not in message)

same=handler.redirect_request(req,None,302,'Found',{},'https://power-house.example.invalid:443/releases/b.zip')
ok('same-origin redirect to explicit :443 remains permitted',same.full_url=='https://power-house.example.invalid:443/releases/b.zip')
ok('same-origin :443 redirect retains bearer authentication',same.get_header('Authorization')=='Bearer '+TOKEN)

# Preserve support for an explicitly configured non-default deployment-controlled
# Power House origin. The configured port must match exactly; absence or another port cannot.
old_base=os.environ['SCOREMAX_POWER_HOUSE_BASE_URL']
os.environ['SCOREMAX_POWER_HOUSE_BASE_URL']='https://power-house.example.invalid:8443'
try:
    u,o=integ._validate_power_house_package_url('https://power-house.example.invalid:8443/pkg.zip')
    ok('configured non-default trusted port remains supported',o==('https','power-house.example.invalid',8443) and ':8443/' in u)
    rejected_missing=False
    try: integ._validate_power_house_package_url('https://power-house.example.invalid/pkg.zip')
    except ValueError: rejected_missing=True
    ok('configured non-default trusted port cannot be bypassed by omitted port',rejected_missing)
finally:
    os.environ['SCOREMAX_POWER_HOUSE_BASE_URL']=old_base

# Durable-state hygiene and DB gates.
dump='\n'.join(c.iterdump())
ok('no bearer token in durable database evidence',TOKEN not in dump)
integrity=c.execute('PRAGMA integrity_check').fetchone()[0]
fk=len(c.execute('PRAGMA foreign_key_check').fetchall())
ok('V6.5.6 explicit-port DB integrity remains clean',integrity=='ok')
ok('V6.5.6 explicit-port FK violations remain zero',fk==0)
print(f'\nSCOREMAX V6.5.6 EXPLICIT-PORT NORMALISATION CHECKS PASSED: {N}')
print('confirmed_total=0 · P0=0 · P1=0 · integrity=%s · foreign_key_violations=%d'%(integrity,fk))
c.close()
