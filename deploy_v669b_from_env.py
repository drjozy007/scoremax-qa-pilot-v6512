from __future__ import annotations
import base64, hashlib, io, os, shutil, tarfile, zipfile
from pathlib import Path

PAYLOAD_SHA='aa7bf37c677385396de0b01e83fd0b91ead35abc87847bc01ae74e64bd0d2b74'
HERO_SHA='ada647f2678abcb08f3423394422cceea8d2c81f5eaf14b57c328bf3d1d591d5'
SOURCE_SHA='70a181237cd028b86f34650b0fbc912174ee1516965dd62f8d4b2862bea63ffa'
BASE=Path('SCOREMAX_ONLY_UPLOAD_TO_GITHUB_V6_5_12.zip')
OUT=Path('scoremax_runtime_v669b')
PAYLOAD_DIR=Path('runtime_payload')
HERO='static/scoremax_intelligence_hero.png'
TEXT_COUNT=183
RUNTIME_COUNT=184

def sha(b): return hashlib.sha256(b).hexdigest()
def fsha(p): return sha(Path(p).read_bytes())

def hero_from_zip(raw, depth=0):
    if depth>6: return None
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            for i in z.infolist():
                if i.filename.replace('\\','/').endswith(HERO):
                    b=z.read(i)
                    if sha(b)==HERO_SHA: return b
            for i in z.infolist():
                if i.filename.lower().endswith('.zip') and i.file_size < 50_000_000:
                    b=hero_from_zip(z.read(i),depth+1)
                    if b is not None: return b
    except zipfile.BadZipFile: pass
    return None

def decode_candidate(encoded):
    try:
        raw=base64.b64decode(encoded,validate=True)
    except Exception:
        return None
    return raw if sha(raw)==PAYLOAD_SHA else None

def governed_payload():
    keys=sorted(k for k in os.environ if k.startswith('V669B_PAYLOAD_PART_'))
    if keys:
        encoded=''.join(os.environ[k].strip() for k in keys)
        raw=decode_candidate(encoded)
        if raw is not None:
            return raw,'environment'
        print('V669B_ENV_PAYLOAD_REJECTED_FALLING_BACK_TO_COMMITTED_PARTS')
    parts=sorted(PAYLOAD_DIR.glob('v669b_text_runtime.b64.part*'))
    if not parts:
        raise SystemExit('V669B_COMMITTED_PAYLOAD_MISSING')
    encoded=''.join(p.read_text(encoding='ascii').strip() for p in parts)
    raw=decode_candidate(encoded)
    if raw is None:
        raise SystemExit('V669B_COMMITTED_PAYLOAD_INVALID_OR_SHA_MISMATCH')
    return raw,'committed_parts'

def main():
    raw,transport=governed_payload()
    shutil.rmtree(OUT,ignore_errors=True); OUT.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(raw),mode='r:xz') as t:
        for m in t.getmembers():
            p=(OUT/m.name).resolve()
            if OUT.resolve() not in p.parents and p!=OUT.resolve(): raise SystemExit('V669B_UNSAFE_TAR')
        t.extractall(OUT)
    if len([p for p in OUT.rglob('*') if p.is_file()])!=TEXT_COUNT: raise SystemExit('V669B_TEXT_COUNT_MISMATCH')
    if not BASE.is_file(): raise SystemExit('V6512_BASE_MISSING')
    hb=hero_from_zip(BASE.read_bytes())
    if hb is None: raise SystemExit('V669B_HERO_NOT_FOUND')
    hp=OUT/HERO; hp.parent.mkdir(parents=True,exist_ok=True); hp.write_bytes(hb)
    if fsha(hp)!=HERO_SHA: raise SystemExit('V669B_HERO_SHA_MISMATCH')
    files=[p for p in OUT.rglob('*') if p.is_file()]
    if len(files)!=RUNTIME_COUNT: raise SystemExit('V669B_RUNTIME_COUNT_MISMATCH')
    mp=OUT/'V6_6_9B_PACKAGE_MANIFEST.json'
    if not mp.is_file() or '6.6.9B' not in mp.read_text(encoding='utf-8'): raise SystemExit('V669B_RELEASE_IDENTITY_MISSING')
    for r in ('app.py','scoremax_production.py','production_infrastructure_engine.py','production_qualification_engine.py','scoremax_integration_v1.py','feature_availability_engine.py','science_genius_engine.py','digital_coach_engine.py','requirements.txt','Procfile'):
        if not (OUT/r).is_file(): raise SystemExit('V669B_REQUIRED_FILE_MISSING:'+r)
    print('V669B_HOSTED_RUNTIME_VERIFIED', 'payload_sha256='+PAYLOAD_SHA, 'source_candidate_sha256='+SOURCE_SHA, 'hero_sha256='+HERO_SHA, 'files='+str(len(files)), 'payload_transport='+transport, 'status=DEPENDENT_CANDIDATE_NOT_FROZEN')
if __name__=='__main__': main()
