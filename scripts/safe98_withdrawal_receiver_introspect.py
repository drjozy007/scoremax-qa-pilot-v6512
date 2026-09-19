#!/usr/bin/env python3
from __future__ import annotations
import json, os, sqlite3
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/"scoremax_runtime_v669b"
DB=Path(os.environ["SCOREMAX_DB"]).resolve()
TERMS=[
 "PH_SM_QUESTION_WITHDRAWAL_V1",
 "/api/integration/v1/power-house/question-withdrawals",
 "STOP_FUTURE_DELIVERY_PRESERVE_HISTORICAL_ATTEMPTS",
 "historical_attempts_must_be_preserved",
 "def admit_withdrawal_envelope",
 "question_version_fingerprint",
 "ph_bridge_withdrawal_receipts_v6611d",
]
RELEASE_ID="REL::PILOT::BIO12-CH13::SAFE98::20260919"
RELEASE_VERSION="1"
TARGET="PH-RS-Q-1E94CCFE2E15F0E679D9FC"
TARGET_VERSION="QV::PH-RS-Q-1E94CCFE2E15F0E679D9FC::v1"

def canon(v): return json.dumps(v,sort_keys=True,separators=(",",":"),ensure_ascii=False,default=str)

def source_hits():
    out=[]
    for p in sorted(RUNTIME.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in {".py",".json",".txt",".html",".js"}: continue
        try: s=p.read_text(encoding="utf-8",errors="replace")
        except Exception: continue
        found=[t for t in TERMS if t in s]
        if not found: continue
        snippets=[]
        for t in found:
            i=s.find(t); a=max(0,i-1200); b=min(len(s),i+3500)
            snippets.append({"term":t,"snippet":s[a:b]})
        out.append({"path":p.relative_to(ROOT).as_posix(),"terms":found,"snippets":snippets})
    return out

def db_state():
    c=sqlite3.connect(DB,timeout=30); c.row_factory=sqlite3.Row
    try:
        tables=[r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
        rel={}
        for t in tables:
            lt=t.lower()
            if not any(k in lt for k in ("withdraw","release","membership","activation","receipt","audit")): continue
            cols=[r[1] for r in c.execute(f"PRAGMA table_info({t})").fetchall()]
            rel[t]={"columns":cols}
            probes=[]
            try:
                if "release_id" in cols and "release_version" in cols:
                    n=c.execute(f"SELECT COUNT(*) FROM {t} WHERE release_id=? AND release_version=?",(RELEASE_ID,RELEASE_VERSION)).fetchone()[0]
                    probes.append({"kind":"release","count":int(n)})
                if "question_id" in cols and "question_version_id" in cols:
                    n=c.execute(f"SELECT COUNT(*) FROM {t} WHERE question_id=? AND question_version_id=?",(TARGET,TARGET_VERSION)).fetchone()[0]
                    probes.append({"kind":"question","count":int(n)})
                elif "question_id" in cols:
                    n=c.execute(f"SELECT COUNT(*) FROM {t} WHERE question_id=?",(TARGET,)).fetchone()[0]
                    probes.append({"kind":"question","count":int(n)})
            except Exception as exc:
                probes.append({"kind":"error","error":type(exc).__name__})
            if probes: rel[t]["probes"]=probes
        state={}
        if "integration_ph_content_releases" in tables:
            r=c.execute("SELECT local_status,release_status,question_count,activated_at,withdrawn_at,withdrawal_reason,package_checksum_sha256 FROM integration_ph_content_releases WHERE release_id=? AND release_version=?",(RELEASE_ID,RELEASE_VERSION)).fetchone()
            if r: state["release"]=dict(r)
        if "integration_ph_release_question_membership" in tables:
            r=c.execute("""SELECT * FROM integration_ph_release_question_membership
                           WHERE release_id=? AND release_version=? AND question_id=? AND question_version_id=?""",
                        (RELEASE_ID,RELEASE_VERSION,TARGET,TARGET_VERSION)).fetchone()
            if r: state["target_membership"]=dict(r)
            state["membership_count"]=int(c.execute("SELECT COUNT(*) FROM integration_ph_release_question_membership WHERE release_id=? AND release_version=?",(RELEASE_ID,RELEASE_VERSION)).fetchone()[0])
        if "integration_ph_product_activation_authorizations" in tables:
            state["activation_authorizations"]=int(c.execute("SELECT COUNT(*) FROM integration_ph_product_activation_authorizations WHERE release_id=? AND release_version=?",(RELEASE_ID,RELEASE_VERSION)).fetchone()[0])
        state["quick_check"]=c.execute("PRAGMA quick_check").fetchone()[0]
        state["fk"]=len(c.execute("PRAGMA foreign_key_check").fetchall())
        concise_tables={}
        for name in ("ph_bridge_withdrawal_receipts_v6611d","integration_ph_content_releases","integration_ph_release_question_membership","integration_ph_product_activation_authorizations"):
            if name in rel: concise_tables[name]=rel[name]
        return {"relevant_tables":concise_tables,"state":state}
    finally: c.close()

def main():
    result={
      "marker":"SCOREMAX_SAFE98_WITHDRAWAL_RECEIVER_INTROSPECT_V1",
      "source_hits":[{"path":x["path"],"terms":x["terms"],"snippets":[{"term":y["term"],"snippet":y["snippet"][:1600]} for y in x["snippets"]]} for x in source_hits()],
      "db":db_state(),
      "mutated":False
    }
    print("SCOREMAX_SAFE98_WITHDRAWAL_RECEIVER_INTROSPECT "+canon(result),flush=True)
    return 0

if __name__=="__main__": raise SystemExit(main())
