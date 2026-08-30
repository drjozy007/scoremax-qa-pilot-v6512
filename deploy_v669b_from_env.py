from __future__ import annotations
import base64,hashlib,io,json,os,shutil,subprocess,tarfile
from pathlib import Path

BASE=Path('hosted_runtime_base_v6512')
OUT=Path('scoremax_runtime_v669b')  # Render service path retained; final bytes are V6.6.10G
PATHS_FILE=Path('qualification/v6610f_runtime_paths.json')
OVERLAY_DIR=Path('runtime_overlay')
DELTA_SHA='5f20e0ca9219c40bb0ffe0470c076a911c70ee3c8ddef9e40bdc74b797e131a2'
TREE_SHA='e4de5db8fc107a1e1485550b904040df328f76266518abb183daec029dd9c0c1'
SOURCE_ZIP_SHA='6dc69467b01016d32da8775eb6e79d9b3e008208408ddaa3115a14adcc9b52d0'
HERO_SHA='ada647f2678abcb08f3423394422cceea8d2c81f5eaf14b57c328bf3d1d591d5'
RELEASE='6.6.10G'

def sha(b): return hashlib.sha256(b).hexdigest()
def fsha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    return h.hexdigest()

def safe_extract(raw,out):
    with tarfile.open(fileobj=io.BytesIO(raw),mode='r:xz') as tf:
        root=Path(out).resolve()
        for m in tf.getmembers():
            p=(Path(out)/m.name).resolve()
            if root not in p.parents and p!=root: raise SystemExit('V6610G_UNSAFE_TAR:'+m.name)
        tf.extractall(out)

def main():
    if not BASE.is_dir(): raise SystemExit('V6610G_BASELINE_MISSING')
    # Derive exact 10G production-runtime path set from the already governed 10F contract.
    paths=set(json.loads(PATHS_FILE.read_text(encoding='utf-8')))
    paths.discard('README_SCOREMAX_V6_6_9B.md')
    paths.discard('V6_6_9B_PACKAGE_MANIFEST.json')
    paths.add('production_content_seed_policy.py')
    if len(paths)!=188: raise SystemExit(f'V6610G_PATH_CONTRACT_INVALID got={len(paths)} expected=188')

    shutil.rmtree(OUT,ignore_errors=True); OUT.mkdir(parents=True)
    for rel in sorted(paths):
        src=BASE/rel
        if src.is_file():
            dst=OUT/rel; dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst)

    # Apply the committed, Git-native V6.5.12 -> V6.6.9B overlay.
    old_parts=sorted(OVERLAY_DIR.glob('v669b_overlay.b64.part*'))
    if len(old_parts)!=3: raise SystemExit(f'V669B_COMMITTED_OVERLAY_PART_COUNT_MISMATCH got={len(old_parts)} expected=3')
    old_encoded=''.join(p.read_text(encoding='ascii').strip() for p in old_parts)
    try: old_raw=base64.b64decode(old_encoded,validate=True)
    except Exception as exc: raise SystemExit(f'V669B_COMMITTED_OVERLAY_BASE64_INVALID:{type(exc).__name__}') from exc
    safe_extract(old_raw,OUT)

    # Apply the small exact V6.6.9B -> V6.6.10G runtime delta supplied through bounded Render values.
    keys=sorted(k for k in os.environ if k.startswith('V6610G_DELTA_PART_'))
    if len(keys)!=4: raise SystemExit(f'V6610G_DELTA_PART_COUNT_MISMATCH got={len(keys)} expected=4')
    vals=[os.environ[k].strip() for k in keys]
    if any(len(v)>9000 for v in vals): raise SystemExit('V6610G_DELTA_PART_OVERSIZE')
    encoded=''.join(vals)
    try: delta_raw=base64.b64decode(encoded,validate=True)
    except Exception as exc: raise SystemExit(f'V6610G_DELTA_BASE64_INVALID:{type(exc).__name__}') from exc
    got=sha(delta_raw)
    if got!=DELTA_SHA: raise SystemExit(f'V6610G_DELTA_SHA_MISMATCH got={got} expected={DELTA_SHA}')
    tmp=Path('/tmp/v6610g_delta'); shutil.rmtree(tmp,ignore_errors=True); tmp.mkdir(parents=True)
    safe_extract(delta_raw,tmp)
    patch=tmp/'v669b_to_v6610g_runtime.patch'
    if not patch.is_file(): raise SystemExit('V6610G_DELTA_PATCH_MISSING')
    cp=subprocess.run(['patch','-d',str(OUT),'-p1','--batch','--forward'],input=patch.read_bytes(),stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    if cp.returncode!=0: raise SystemExit('V6610G_PATCH_FAILED:'+cp.stdout.decode(errors='replace')[-1600:])
    new_root=tmp/'new'
    for p in sorted(new_root.rglob('*')):
        if p.is_file():
            rel=p.relative_to(new_root)
            dst=OUT/rel; dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(p,dst)

    actual=sorted(p.relative_to(OUT).as_posix() for p in OUT.rglob('*') if p.is_file())
    if actual!=sorted(paths):
        missing=sorted(paths-set(actual)); extra=sorted(set(actual)-paths)
        raise SystemExit(f'V6610G_RUNTIME_PATH_SET_MISMATCH actual={len(actual)} expected={len(paths)} missing={missing[:8]} extra={extra[:8]}')
    tree=hashlib.sha256()
    for rel in sorted(paths):
        p=OUT/rel; tree.update(f'{rel}\0{fsha(p)}\0{p.stat().st_size}\n'.encode())
    got_tree=tree.hexdigest()
    if got_tree!=TREE_SHA: raise SystemExit(f'V6610G_RUNTIME_TREE_SHA_MISMATCH got={got_tree} expected={TREE_SHA}')
    if fsha(OUT/'static/scoremax_intelligence_hero.png')!=HERO_SHA: raise SystemExit('V6610G_HERO_SHA_MISMATCH')
    req=(OUT/'requirements.txt').read_text(encoding='utf-8')
    if 'Flask==3.1.3' not in req or 'Werkzeug==3.1.6' not in req: raise SystemExit('V6610G_DEPENDENCY_SECURITY_PINS_MISSING')
    app=(OUT/'app.py').read_text(encoding='utf-8')
    integ=(OUT/'scoremax_integration_v1.py').read_text(encoding='utf-8')
    if "SCOREMAX_RELEASE_VERSION='6.6.10G'" not in app or '6.6.10G' not in integ: raise SystemExit('V6610G_RELEASE_IDENTITY_MISSING')
    for reqfile in ('scoremax_production.py','scoremax_production_entrypoint.py','production_content_seed_policy.py','request_security_engine.py','security_rate_limit_engine.py','public_origin_engine.py','referral_attribution_engine.py'):
        if not (OUT/reqfile).is_file(): raise SystemExit('V6610G_REQUIRED_FILE_MISSING:'+reqfile)
    print('V6610G_GITNATIVE_RUNTIME_VERIFIED',f'source_zip_sha256={SOURCE_ZIP_SHA}',f'delta_sha256={DELTA_SHA}',f'runtime_tree_sha256={TREE_SHA}',f'files={len(paths)}',f'release={RELEASE}','status=PREQUALIFICATION_CANDIDATE_NOT_CURRENT_HEAD_NOT_FROZEN')

if __name__=='__main__': main()
