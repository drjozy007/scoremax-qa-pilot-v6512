from __future__ import annotations
import base64, hashlib, io, json, lzma, os, shutil, tarfile, zipfile
from pathlib import Path

RELEASE='6.6.10G'
PAYLOAD_SHA='49c1039ca446675506da9a986e97d7808224628b17053c3d6f887ecd4becb9ca'
SOURCE_ZIP_SHA='6dc69467b01016d32da8775eb6e79d9b3e008208408ddaa3115a14adcc9b52d0'
PACKAGE_MANIFEST_SHA='ce1c970123468cd6a7f22abf0563cdef87c7bcd771819ec5b850f6f49c635074'
HERO_SHA='ada647f2678abcb08f3423394422cceea8d2c81f5eaf14b57c328bf3d1d591d5'
BASE=Path('SCOREMAX_ONLY_UPLOAD_TO_GITHUB_V6_5_12.zip')
OUT=Path('scoremax_runtime_v669b')  # retained service path; reconstructed bytes are V6.6.10G
HERO='static/scoremax_intelligence_hero.png'
TEXT_COUNT=189
RUNTIME_COUNT=190

def sha(b): return hashlib.sha256(b).hexdigest()
def fsha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    return h.hexdigest()

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

def governed_payload():
    keys=sorted(k for k in os.environ if k.startswith('V6610G_PAYLOAD_PART_'))
    if len(keys)!=66:
        raise SystemExit(f'V6610G_ENV_PAYLOAD_PART_COUNT_MISMATCH got={len(keys)} expected=66')
    vals=[os.environ[k].strip() for k in keys]
    if any(len(v)>9000 for v in vals):
        raise SystemExit('V6610G_ENV_PAYLOAD_PART_OVERSIZE')
    encoded=''.join(vals)
    print('V6610G_ENV_PAYLOAD_OBSERVED','parts='+str(len(keys)),'total='+str(len(encoded)))
    try: raw=base64.b64decode(encoded,validate=True)
    except Exception as exc: raise SystemExit(f'V6610G_ENV_PAYLOAD_BASE64_INVALID:{type(exc).__name__}') from exc
    got=sha(raw)
    if got!=PAYLOAD_SHA: raise SystemExit(f'V6610G_ENV_PAYLOAD_SHA_MISMATCH got={got} expected={PAYLOAD_SHA}')
    return raw

def main():
    compressed=governed_payload()
    try: tar_raw=lzma.decompress(compressed)
    except Exception as exc: raise SystemExit(f'V6610G_XZ_INVALID:{type(exc).__name__}') from exc
    shutil.rmtree(OUT,ignore_errors=True); OUT.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(tar_raw),mode='r:') as t:
        root=OUT.resolve()
        for m in t.getmembers():
            p=(OUT/m.name).resolve()
            if root not in p.parents and p!=root: raise SystemExit('V6610G_UNSAFE_TAR:'+m.name)
        t.extractall(OUT)
    text_files=[p for p in OUT.rglob('*') if p.is_file()]
    if len(text_files)!=TEXT_COUNT: raise SystemExit(f'V6610G_TEXT_COUNT_MISMATCH got={len(text_files)} expected={TEXT_COUNT}')
    mp=OUT/'V6_6_10G_PACKAGE_MANIFEST.json'
    if not mp.is_file() or fsha(mp)!=PACKAGE_MANIFEST_SHA: raise SystemExit('V6610G_PACKAGE_MANIFEST_SHA_MISMATCH')
    manifest=json.loads(mp.read_text(encoding='utf-8'))
    if manifest.get('release')!=RELEASE: raise SystemExit('V6610G_PACKAGE_MANIFEST_RELEASE_MISMATCH')
    expected={e['path']:e['sha256'] for e in manifest.get('members',[]) if isinstance(e,dict) and isinstance(e.get('path'),str) and isinstance(e.get('sha256'),str)}
    for p in text_files:
        rel=p.relative_to(OUT).as_posix()
        if rel=='V6_6_10G_PACKAGE_MANIFEST.json': continue
        want=expected.get(rel)
        if not want: raise SystemExit('V6610G_PAYLOAD_FILE_NOT_IN_PACKAGE_MANIFEST:'+rel)
        got=fsha(p)
        if got!=want: raise SystemExit(f'V6610G_PAYLOAD_FILE_SHA_MISMATCH path={rel} got={got} expected={want}')
    if not BASE.is_file(): raise SystemExit('V6512_BASE_MISSING_FOR_HERO_REUSE')
    hb=hero_from_zip(BASE.read_bytes())
    if hb is None: raise SystemExit('V6610G_VERIFIED_HERO_NOT_FOUND')
    hp=OUT/HERO; hp.parent.mkdir(parents=True,exist_ok=True); hp.write_bytes(hb)
    if fsha(hp)!=HERO_SHA: raise SystemExit('V6610G_HERO_SHA_MISMATCH')
    files=[p for p in OUT.rglob('*') if p.is_file()]
    if len(files)!=RUNTIME_COUNT: raise SystemExit(f'V6610G_RUNTIME_COUNT_MISMATCH got={len(files)} expected={RUNTIME_COUNT}')
    required=('app.py','scoremax_production.py','scoremax_production_entrypoint.py','production_content_seed_policy.py','production_infrastructure_engine.py','production_qualification_engine.py','scoremax_integration_v1.py','feature_availability_engine.py','science_genius_engine.py','digital_coach_engine.py','referral_attribution_engine.py','public_origin_engine.py','request_security_engine.py','security_rate_limit_engine.py','requirements.txt','Procfile')
    for r in required:
        if not (OUT/r).is_file(): raise SystemExit('V6610G_REQUIRED_FILE_MISSING:'+r)
    req=(OUT/'requirements.txt').read_text(encoding='utf-8')
    if 'Flask==3.1.3' not in req or 'Werkzeug==3.1.6' not in req: raise SystemExit('V6610G_DEPENDENCY_SECURITY_PINS_MISSING')
    app=(OUT/'app.py').read_text(encoding='utf-8')
    integ=(OUT/'scoremax_integration_v1.py').read_text(encoding='utf-8')
    if "SCOREMAX_RELEASE_VERSION='6.6.10G'" not in app or '6.6.10G' not in integ: raise SystemExit('V6610G_RELEASE_IDENTITY_MISSING')
    print('V6610G_HOSTED_RUNTIME_VERIFIED','payload_sha256='+PAYLOAD_SHA,'source_candidate_sha256='+SOURCE_ZIP_SHA,'hero_sha256='+HERO_SHA,'files='+str(len(files)),'release='+RELEASE,'status=PREQUALIFICATION_CANDIDATE_NOT_CURRENT_HEAD_NOT_FROZEN')
if __name__=='__main__': main()
