"""Test-only reuse of the EXISTING ScoreMax written-AI owned_material authority.

The 23 Nov Render assembly intentionally contains no paid written-AI hook. This
prepare step installs the already-reviewed adapter, with paid AI OFF, solely in a
checksum-verified, disposable UK11 CI runtime. No contract, marking, source DB,
or public deployment is modified.
"""
from __future__ import annotations
from pathlib import Path
import ast
import hashlib
import json
import shutil

EXPECTED_SOURCE_BLOB='aafcde0e572ac8967b025315f7c4b23c136f1f1f'
WSGI_ANCHOR='application=scoremax.app\napp=application'
WRITTEN_INSTALL='from written_ai_adapter import install as install_written_ai\ninstall_written_ai(scoremax)\n'


def git_blob_sha(raw):
    return hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()


def prepare(root,source):
    root=Path(root).resolve(strict=True)
    source=Path(source).resolve(strict=True)
    if not (root/'.uk11_disposable_qualification_runtime').is_file():
        raise RuntimeError('DISPOSABLE_RUNTIME_REQUIRED')
    path=source/'written_ai_adapter.py'
    if not path.is_file():raise RuntimeError('EXISTING_WRITTEN_AI_ADAPTER_MISSING')
    raw=path.read_bytes()
    if git_blob_sha(raw)!=EXPECTED_SOURCE_BLOB:
        raise RuntimeError('EXISTING_WRITTEN_AI_ADAPTER_SOURCE_DRIFT')
    adapter_target=root/'written_ai_adapter.py'
    if adapter_target.exists():
        if adapter_target.read_bytes()!=raw:
            raise RuntimeError('NATIVE_WRITTEN_AI_ADAPTER_CONFLICT')
    wsgi=root/'scoremax_production.py'
    text=wsgi.read_text(encoding='utf8')
    if WRITTEN_INSTALL in text:
        raise RuntimeError('NATIVE_WRITTEN_AI_ALREADY_INSTALLED')
    if text.count(WSGI_ANCHOR)!=1:
        raise RuntimeError('NATIVE_WSGI_INSERT_ANCHOR_DRIFT')
    ast.parse(raw.decode('utf8'))
    updated=text.replace(WSGI_ANCHOR,WRITTEN_INSTALL+WSGI_ANCHOR,1)
    ast.parse(updated)
    before=wsgi.read_bytes()
    created=False
    try:
        if not adapter_target.exists():
            adapter_target.write_bytes(raw)
            created=True
        wsgi.write_text(updated,encoding='utf8',newline='\n')
    except BaseException:
        wsgi.write_bytes(before)
        if created:adapter_target.unlink(missing_ok=True)
        raise
    return dict(mode='DISPOSABLE_REUSE_EXISTING_WRITTEN_AI_OWNER_ONLY',
                adapter_blob_sha=EXPECTED_SOURCE_BLOB,
                service_environment_changes=0,default_provider_calls=0,
                production_runtime_changes=0,new_database_tables=0)

if __name__=='__main__':
    import sys
    print(json.dumps(prepare(sys.argv[1],sys.argv[2]),sort_keys=True))
