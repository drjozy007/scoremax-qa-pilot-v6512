"""ScoreMax V6.5.5 permanent regression for INT-SM654-P0-001.

Proves Power House MANIFEST_PULL bearer credentials are never exposed to an
attacker-controlled origin or cross-origin redirect, while same-origin package
pull authentication, checksum verification, and staging remain functional.
Disposable database only; no external network is used.
"""
from __future__ import annotations
from release_compatibility import is_compatible_descendant
import copy, json, os, sys, tempfile
from pathlib import Path

TMP=Path(tempfile.mkdtemp(prefix='scoremax_v655_origin_'))
ROOT=Path(__file__).resolve().parent
TOKEN='V655-PH-BEARER-SECRET-MUST-NEVER-LEAK'
os.environ.update({
    'SCOREMAX_DB':str(TMP/'scoremax.db'),
    'SCOREMAX_SECRET':'V655-Origin-Security-Disposable-Secret',
    'SCOREMAX_ENV':'test','SCOREMAX_ENFORCE_PAYWALL':'0','SCOREMAX_INTERNAL_FULL_ACCESS':'1',
    'SCOREMAX_POWER_HOUSE_BASE_URL':'https://power-house.example.invalid',
    'SCOREMAX_TO_POWER_HOUSE_TOKEN':TOKEN,
    'SCOREMAX_TO_POWER_HOUSE_HMAC_SECRET':'v655-sm-ph-secret-long-enough-for-hmac',
    'POWER_HOUSE_TO_SCOREMAX_TOKEN':'v655-ph-token-long-enough',
    'POWER_HOUSE_TO_SCOREMAX_HMAC_SECRET':'v655-ph-secret-long-enough-for-hmac',
    'SCOREMAX_GROWTH_ENGINE_BASE_URL':'https://growth.example.invalid',
    'SCOREMAX_TO_GROWTH_ENGINE_TOKEN':'v655-growth-token-long-enough',
    'SCOREMAX_TO_GROWTH_ENGINE_HMAC_SECRET':'v655-growth-secret-long-enough-for-hmac',
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

ok('V6.5.5 origin-security suite remains active in descendant',is_compatible_descendant(app.SCOREMAX_RELEASE_VERSION,'6.5.5') and is_compatible_descendant(integ.SCOREMAX_INTEGRATION_RELEASE,'6.5.5'))

# Direct-origin attack family: validation MUST happen before credential read and before opener/network.
orig_cred=integ._manifest_pull_credentials
orig_build=integ.urlrequest.build_opener
for label,bad in [
    ('direct cross-origin','https://attacker.invalid/pkg.zip'),
    ('suffix host confusion','https://power-house.example.invalid.attacker.invalid/pkg.zip'),
    ('userinfo confusion','https://power-house.example.invalid@attacker.invalid/pkg.zip'),
    ('unexpected port','https://power-house.example.invalid:444/pkg.zip'),
    ('non-HTTPS','http://power-house.example.invalid/pkg.zip'),
]:
    calls={'cred':0,'open':0}
    def no_cred():
        calls['cred']+=1
        raise AssertionError('credential accessed before URL trust validation')
    def no_open(*a,**k):
        calls['open']+=1
        raise AssertionError('network/opener created before URL trust validation')
    integ._manifest_pull_credentials=no_cred
    integ.urlrequest.build_opener=no_open
    blocked=False
    try: integ._download_manifest_package(bad,timeout=1)
    except ValueError: blocked=True
    finally:
        integ._manifest_pull_credentials=orig_cred
        integ.urlrequest.build_opener=orig_build
    ok(label+' blocked',blocked)
    ok(label+' fails before credential access and network',calls=={'cred':0,'open':0})

# Deployment-controlled base URL itself must also be HTTPS/unambiguous before credential access.
old_base=os.environ['SCOREMAX_POWER_HOUSE_BASE_URL']
os.environ['SCOREMAX_POWER_HOUSE_BASE_URL']='http://power-house.example.invalid'
calls={'cred':0,'open':0}
def no_cred2(): calls.__setitem__('cred',calls['cred']+1); raise AssertionError('credential read')
def no_open2(*a,**k): calls.__setitem__('open',calls['open']+1); raise AssertionError('opener built')
integ._manifest_pull_credentials=no_cred2; integ.urlrequest.build_opener=no_open2
blocked=False
try: integ._download_manifest_package('https://power-house.example.invalid/pkg.zip',timeout=1)
except ValueError: blocked=True
finally:
    integ._manifest_pull_credentials=orig_cred; integ.urlrequest.build_opener=orig_build; os.environ['SCOREMAX_POWER_HOUSE_BASE_URL']=old_base
ok('misconfigured non-HTTPS trusted origin fails closed before secret/network',blocked and calls=={'cred':0,'open':0})

# Cross-origin redirects are rejected by the redirect policy before urllib can construct a redirected request.
origin=integ._trusted_power_house_origin()
handler=integ._PowerHouseSameOriginRedirectHandler(origin)
req=integ.urlrequest.Request('https://power-house.example.invalid/releases/a.zip',headers={'Authorization':'Bearer '+TOKEN},method='GET')
blocked=False
try: handler.redirect_request(req,None,302,'Found',{},'https://attacker.invalid/steal')
except ValueError: blocked=True
ok('cross-origin redirect credential leakage blocked',blocked)

# Same-origin redirects remain permitted and preserve authenticated request semantics.
same=handler.redirect_request(req,None,302,'Found',{},'https://power-house.example.invalid/releases/b.zip')
ok('same-origin redirect remains permitted',same.full_url=='https://power-house.example.invalid/releases/b.zip')
ok('same-origin redirect retains bearer authentication',same.get_header('Authorization')=='Bearer '+TOKEN)

# Full legitimate MANIFEST_PULL: authentication + governed checksums + staging.
example=json.loads((ROOT/'integration_examples/v1_1_0/PH_SM_APPROVED_CONTENT_V1_1_MANIFEST_PULL.example.json').read_text(encoding='utf-8'))
package_bytes=(ROOT/'integration_examples/v1_1_0/PH_SM_APPROVED_CONTENT_MANIFEST_DEMO_v1_1_0.zip').read_bytes()
class FakeResponse:
    status=200
    def __enter__(self): return self
    def __exit__(self,*a): return False
    def read(self): return package_bytes
class FakeOpener:
    def __init__(self): self.req=None; self.timeout=None
    def open(self,req,timeout=None): self.req=req; self.timeout=timeout; return FakeResponse()
fake=FakeOpener()
integ.urlrequest.build_opener=lambda *handlers: fake
try:
    rec,status=integ.admit_content_envelope(c,copy.deepcopy(example),example['payload_checksum_sha256'])
finally:
    integ.urlrequest.build_opener=orig_build
ok('legitimate same-origin manifest pull accepted',status in (200,202) and rec['status'] in ('ACCEPTED','DUPLICATE'))
ok('legitimate same-origin pull authenticates to Power House',fake.req is not None and fake.req.full_url.startswith('https://power-house.example.invalid/') and fake.req.get_header('Authorization')=='Bearer '+TOKEN)
rel=example['payload']['release']
staged=c.execute('SELECT local_status,package_checksum_sha256,manifest_checksum_sha256 FROM integration_ph_content_releases WHERE release_id=? AND release_version=?',(rel['release_id'],rel['release_version'])).fetchone()
qcount=c.execute('SELECT COUNT(*) n FROM integration_ph_release_question_membership WHERE release_id=? AND release_version=?',(rel['release_id'],rel['release_version'])).fetchone()['n']
ok('same-origin package checksum and manifest checksum verified before staging',bool(staged) and staged['package_checksum_sha256']==rel['package_checksum_sha256'] and staged['manifest_checksum_sha256']==rel['manifest_checksum_sha256'])
ok('same-origin governed question staged',int(qcount)==int(rel['question_count'])==1)

# Wrong-origin admission returns a sanitized rejection and must never persist the bearer token.
attack=copy.deepcopy(example)
attack['message_id']='msg::PH::V655::ORIGIN-ATTACK'
attack['idempotency_key']='release::v655::origin-attack'
attack['payload']['package_download_url']='https://attacker.invalid/collect.zip'
attack['payload_checksum_sha256']=integ.payload_checksum(attack['payload'])
cred_calls={'n':0}
def watched_cred(): cred_calls['n']+=1; return TOKEN
integ._manifest_pull_credentials=watched_cred
integ.urlrequest.build_opener=lambda *a,**k: (_ for _ in ()).throw(AssertionError('opener must not be created'))
try:
    rec2,status2=integ.admit_content_envelope(c,attack,attack['payload_checksum_sha256'])
finally:
    integ._manifest_pull_credentials=orig_cred; integ.urlrequest.build_opener=orig_build
ok('wrong-origin admission rejected before bearer access',status2==422 and rec2['status']=='REJECTED' and cred_calls['n']==0)
dump='\n'.join(c.iterdump())+'\n'+integ.canonical_json(rec2)
ok('no bearer token in receipts/quarantine/diagnostics or database evidence',TOKEN not in dump)

integrity=c.execute('PRAGMA integrity_check').fetchone()[0]
fk=len(c.execute('PRAGMA foreign_key_check').fetchall())
ok('V6.5.5 security rectification DB integrity remains clean',integrity=='ok')
ok('V6.5.5 security rectification FK violations remain zero',fk==0)
print(f'\nSCOREMAX V6.5.5 MANIFEST ORIGIN SECURITY CHECKS PASSED: {N}')
print('confirmed_total=0 · P0=0 · P1=0 · integrity=%s · foreign_key_violations=%d'%(integrity,fk))
c.close()
