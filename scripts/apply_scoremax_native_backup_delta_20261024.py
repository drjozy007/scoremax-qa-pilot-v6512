"""Build-only installer for the existing captured630 runtime; no app execution."""
from __future__ import annotations
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import tempfile

BASE_TREE="28aeb812a0ed269840ff73ea45f6864cf78138e57f98ab6c1c69093161ba6279"
PAYLOAD_SHA={
 "app.py":"b4990e12c725c5f46535f82a4d32070019c1a6c96dbc8eabd71095bfcd954b53",
 "pilot_readiness_engine.py":"59e8628ef184c8e2376252e159d7936600b4ca0358f1f7340c6274de6ea105e7",
 "backup_capacity_v1.py":"ebb95b113285ae6dd8d3e27eb0c0f537f70eecabd5c728dcae48ef986f4308a3",
}
def digest(raw):return hashlib.sha256(raw).hexdigest()
def tree_digest(manifest):return digest(json.dumps(manifest,sort_keys=True,separators=(",",":")).encode())
def source_manifest(root,*,permitted_names):
    # Enumerate and check authority before reading any assembled-root bytes.
    # Unknown DB/env/static/code files are refused, never opened for hashing.
    sources={}
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or (hasattr(path,"is_junction") and path.is_junction()):
            raise RuntimeError("NATIVE_BACKUP_BUILD_ALIAS_REFUSED")
        if path.is_file():
            relative=path.relative_to(root).as_posix()
            if path.suffix==".pyc":
                try:
                    source=(Path(importlib.util.source_from_cache(str(path)))
                            if path.parent.name=="__pycache__" else path.with_suffix(".py"))
                    owner=source.relative_to(root).as_posix()
                except (ValueError,IndexError):
                    raise RuntimeError("NATIVE_BACKUP_UNKNOWN_BYTECODE_REFUSED") from None
                if owner not in permitted_names:
                    raise RuntimeError("NATIVE_BACKUP_UNKNOWN_BYTECODE_REFUSED")
                continue
            if relative not in permitted_names:
                raise RuntimeError("NATIVE_BACKUP_UNKNOWN_BUILD_FILE_REFUSED")
            sources[relative]=path
    return {name:digest(path.read_bytes()) for name,path in sources.items()}

def apply(runtime_root: Path,*,payload_root: Path|None=None) -> dict:
    """Run after all existing assembly overlays/checks, before importing the app."""
    runtime_root=Path(os.path.abspath(os.fspath(runtime_root)))
    if runtime_root.is_symlink() or (hasattr(runtime_root,"is_junction") and runtime_root.is_junction()) or not runtime_root.is_dir():
        raise RuntimeError("NATIVE_BACKUP_ASSEMBLED_RUNTIME_REQUIRED")
    if payload_root is None:
        payload_root=Path(__file__).resolve().parents[1]/"qualification"/"native_backup_delta_20261024"
    payload_root=Path(payload_root)
    original=json.loads((payload_root/"runtime_capture_manifest_630.json").read_text())
    if len(original)!=259 or tree_digest(original)!=BASE_TREE:
        raise RuntimeError("NATIVE_BACKUP_CAPTURE_MANIFEST_MISMATCH")
    payload={}
    for name,pin in PAYLOAD_SHA.items():
        path=payload_root/name
        if path.is_symlink() or not path.is_file():raise RuntimeError("NATIVE_BACKUP_PAYLOAD_FILE_INVALID")
        payload[name]=path.read_bytes()
        if digest(payload[name])!=pin:raise RuntimeError("NATIVE_BACKUP_PAYLOAD_SHA_MISMATCH:"+name)
    derived={**original,**PAYLOAD_SHA}
    permitted_names=set(derived)
    actual=source_manifest(runtime_root,permitted_names=permitted_names)
    if actual==derived:
        return {"replayed":True,"files":260,"base_tree_sha256":BASE_TREE,"derived_tree_sha256":tree_digest(derived)}
    if actual!=original:
        raise RuntimeError("NATIVE_BACKUP_INPUT_IS_NOT_EXACT_CAPTURED630")
    # All sources and payloads are verified before any replacement. A failed
    # build must be discarded/reassembled; this is not a live-runtime updater.
    with tempfile.TemporaryDirectory(prefix=".native-backup-build-",dir=runtime_root.parent) as folder:
        stage=Path(folder)
        for name,raw in payload.items():(stage/name).write_bytes(raw)
        for name in sorted(payload):os.replace(stage/name,runtime_root/name)
    for name in PAYLOAD_SHA:
        stem=Path(name).stem
        legacy=runtime_root/(stem+".pyc")
        if legacy.exists():legacy.unlink()
        cache=runtime_root/"__pycache__"
        if cache.is_dir():
            for path in cache.glob(stem+".*.pyc"):
                if path.is_symlink():raise RuntimeError("NATIVE_BACKUP_BYTECODE_ALIAS_REFUSED")
                path.unlink()
    if source_manifest(runtime_root,permitted_names=permitted_names)!=derived:
        raise RuntimeError("NATIVE_BACKUP_DERIVED_SOURCE_MISMATCH")
    return {"replayed":False,"files":260,"base_tree_sha256":BASE_TREE,"derived_tree_sha256":tree_digest(derived)}

if __name__=="__main__":
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runtime_root",type=Path)
    parser.add_argument("--payload-root",type=Path)
    args=parser.parse_args()
    print("SCOREMAX_NATIVE_BACKUP_DELTA="+json.dumps(apply(args.runtime_root,payload_root=args.payload_root),sort_keys=True))
