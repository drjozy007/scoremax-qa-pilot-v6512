from __future__ import annotations
import base64,hashlib,io,json,os,shutil,tarfile
from pathlib import Path

BASE=Path("hosted_runtime_base_v6512")
OUT=Path("scoremax_runtime_v6610f")
PATHS_FILE=Path("qualification/v6610f_runtime_paths.json")
GIT_OVERLAY_DIR=Path("qualification/v6610f_overlay")
OVERLAY_SHA="871a7e23a8a941f485152cebcfc5169a44fc168f26ebea41d0907cfa35177177"
TREE_SHA="dc3a3c47e050a6c0b0e51aa6312d195e631700c9f5482dc1fc354f7c5745c7a7"
SOURCE_ZIP_SHA="3d2970ad2106f681527271a9855463cb7799b3dabcea6e32378cb7df2687b57e"

def sha(b): return hashlib.sha256(b).hexdigest()
def fsha(p): return sha(Path(p).read_bytes())

def _overlay_bytes():
    keys=sorted(k for k in os.environ if k.startswith("V6610F_OVERLAY_PART_"))
    if keys:
        encoded="".join(os.environ[k].strip() for k in keys)
        source=f"env:{len(keys)}"
    else:
        parts=sorted(GIT_OVERLAY_DIR.glob("part*.b64"))
        if len(parts)!=7:
            raise SystemExit(f"V6610F_OVERLAY_GIT_PART_COUNT_MISMATCH got={len(parts)} expected=7")
        encoded="".join(p.read_text(encoding="ascii").strip() for p in parts)
        source=f"git:{len(parts)}"
    try:
        raw=base64.b64decode(encoded,validate=True)
    except Exception as exc:
        raise SystemExit(f"V6610F_OVERLAY_BASE64_INVALID:{type(exc).__name__}") from exc
    if sha(raw)!=OVERLAY_SHA:
        raise SystemExit(f"V6610F_OVERLAY_SHA_MISMATCH got={sha(raw)} expected={OVERLAY_SHA}")
    return raw,source

def main():
    if not BASE.is_dir(): raise SystemExit("V6610F_BASELINE_MISSING")
    paths=json.loads(PATHS_FILE.read_text(encoding="utf-8"))
    if len(paths)!=189 or len(set(paths))!=189: raise SystemExit("V6610F_PATH_CONTRACT_INVALID")
    raw,source=_overlay_bytes()
    shutil.rmtree(OUT,ignore_errors=True); OUT.mkdir(parents=True)
    for rel in paths:
        src=BASE/rel
        if src.is_file():
            dst=OUT/rel; dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst)
    with tarfile.open(fileobj=io.BytesIO(raw),mode="r:xz") as tf:
        for m in tf.getmembers():
            p=(OUT/m.name).resolve()
            if OUT.resolve() not in p.parents and p!=OUT.resolve(): raise SystemExit("V6610F_OVERLAY_UNSAFE")
        tf.extractall(OUT)
    actual=sorted(p.relative_to(OUT).as_posix() for p in OUT.rglob("*") if p.is_file())
    if actual!=sorted(paths):
        raise SystemExit(f"V6610F_RUNTIME_PATH_SET_MISMATCH actual={len(actual)} expected={len(paths)}")
    tree=hashlib.sha256()
    for rel in sorted(paths):
        p=OUT/rel; tree.update(f"{rel}\0{fsha(p)}\0{p.stat().st_size}\n".encode())
    got=tree.hexdigest()
    if got!=TREE_SHA: raise SystemExit(f"V6610F_RUNTIME_TREE_SHA_MISMATCH got={got} expected={TREE_SHA}")
    for req in ("app.py","scoremax_production_entrypoint.py","request_security_engine.py","security_rate_limit_engine.py","public_origin_engine.py","referral_attribution_engine.py","requirements.txt"):
        if not (OUT/req).is_file(): raise SystemExit("V6610F_REQUIRED_FILE_MISSING:"+req)
    print("V6610F_HOSTED_RUNTIME_VERIFIED",
          f"source_zip_sha256={SOURCE_ZIP_SHA}",
          f"overlay_sha256={OVERLAY_SHA}",f"runtime_tree_sha256={TREE_SHA}",
          f"transport={source}",f"files={len(paths)}", "status=PREQUALIFICATION_CANDIDATE_NOT_CURRENT_HEAD_NOT_FROZEN")

if __name__=="__main__": main()
