from __future__ import annotations

import hashlib
import hmac
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask, jsonify, request

SCHEMA='PH_BROWSER_QA_REMOTE_CAPTURE_V1'
RESPONSE_SCHEMA='PH_BROWSER_QA_REMOTE_RECEIPT_V1'
app=Flask(__name__)
_gate=threading.BoundedSemaphore(1)
_nonce_lock=threading.Lock()
_nonces={}


def _canonical(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def _origin(v):
    p=urlsplit(str(v or '').strip().rstrip('/'))
    if p.scheme not in {'http','https'} or not p.hostname or p.username or p.password or p.query or p.fragment or p.path not in {'','/'}:
        raise ValueError('Browser QA target must be an absolute HTTP(S) origin')
    port=p.port; default=(p.scheme=='https' and port in {None,443}) or (p.scheme=='http' and port in {None,80})
    return f"{p.scheme.lower()}://{p.hostname.lower() if default else p.hostname.lower()+':'+str(port)}"
def _sig(secret,ts,nonce,body):
    bh=hashlib.sha256(body).hexdigest();payload=f'{ts}\n{nonce}\n{bh}'.encode();return hmac.new(secret.encode(),payload,hashlib.sha256).hexdigest()
def _cfg():
    secret=os.environ.get('POWER_HOUSE_QA_BROWSER_WORKER_SECRET','').strip()
    origins={_origin(x) for x in os.environ.get('POWER_HOUSE_QA_ALLOWED_TARGET_ORIGINS','').split(';') if x.strip()}
    max_items=int(os.environ.get('POWER_HOUSE_QA_REMOTE_SLICE_ITEMS','5') or 5)
    if not secret or not origins or max_items<1 or max_items>20: raise RuntimeError('Browser QA worker configuration invalid')
    return secret,origins,max_items

def _nonce(n,now):
    if not n or len(n)>200: raise PermissionError('Browser QA nonce invalid')
    with _nonce_lock:
        for k,e in list(_nonces.items()):
            if e<now:_nonces.pop(k,None)
        if n in _nonces: raise PermissionError('Browser QA nonce replay rejected')
        _nonces[n]=now+180

def _validate(p,origins,max_items):
    if p.get('schema')!=SCHEMA or str(p.get('capture_type') or '').upper()!='LEARNER': raise ValueError('Unsupported Browser QA request')
    request_id=str(p.get('request_id') or '').strip(); base=_origin(p.get('base_url'))
    if not request_id or base not in origins: raise PermissionError('Browser QA target/request invalid')
    items=p.get('items')
    if not isinstance(items,list) or not items or len(items)>max_items: raise ValueError('Browser QA slice size invalid')
    seen=set(); out=[]
    for x in items:
        q=str(x.get('external_question_id') or '').strip();v=str(x.get('external_version') or '').strip();key=(q,v)
        if not q or not v or key in seen: raise ValueError('Learner QA identity invalid/duplicated')
        seen.add(key);out.append({'external_question_id':q,'external_version':v})
    if not str(p.get('username') or '') or not str(p.get('password') or ''): raise ValueError('Learner QA credentials required')
    return {'schema':SCHEMA,'capture_type':'LEARNER','request_id':request_id,'base_url':base,'username':str(p['username']),'password':str(p['password']),'items':out,'headless':True}

def _run_child(payload):
    cp=subprocess.run([sys.executable,'-m','qa_orch_browser_child'],input=_canonical(payload),text=True,capture_output=True,timeout=int(os.environ.get('POWER_HOUSE_QA_BROWSER_CHILD_TIMEOUT','240')),check=False,cwd=str(Path(__file__).resolve().parent))
    try:r=json.loads(cp.stdout)
    except Exception as exc: raise RuntimeError('Browser child invalid JSON') from exc
    if cp.returncode!=0 or r.get('schema')!='PH_BROWSER_QA_SLICE_CHILD_RECEIPT_V1': raise RuntimeError(f"Browser child failed: {r.get('error_type','Error')}: {r.get('message','unknown')}")
    if r.get('request_id')!=payload['request_id']: raise RuntimeError('Browser child identity mismatch')
    return r

@app.get('/healthz')
def health(): return jsonify({'ok':True,'service':'POWER_HOUSE_STATELESS_BROWSER_QA_WORKER_V015H','database_access':False,'academic_decision_authority':False})

@app.post('/v1/capture-slice')
def capture():
    try:
        secret,origins,max_items=_cfg();raw=request.get_data(cache=False);ts=request.headers.get('X-QA-Timestamp','');nonce=request.headers.get('X-QA-Nonce','');sup=request.headers.get('X-QA-Signature','')
        try: t=int(ts)
        except: raise PermissionError('Browser QA timestamp invalid')
        now=int(time.time())
        if abs(now-t)>90 or not hmac.compare_digest(_sig(secret,ts,nonce,raw),str(sup)): raise PermissionError('Browser QA HMAC authentication failed')
        _nonce(nonce,now);payload=_validate(json.loads(raw),origins,max_items)
        if not _gate.acquire(blocking=False): return jsonify({'error':'browser_worker_busy'}),429
        try: child=_run_child(payload)
        finally: _gate.release()
        return jsonify({'schema':RESPONSE_SCHEMA,'request_id':payload['request_id'],'capture_type':'LEARNER','evidence':child['evidence'],'worker_stateless':True,'database_access':False,'academic_decision_authority':False}),200
    except PermissionError as e:return jsonify({'error':str(e)}),403
    except (ValueError,json.JSONDecodeError) as e:return jsonify({'error':str(e)}),400
    except subprocess.TimeoutExpired:return jsonify({'error':'browser_child_timeout'}),504
    except Exception as e:return jsonify({'error':f'{type(e).__name__}: {e}'}),500
