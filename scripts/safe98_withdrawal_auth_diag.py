#!/usr/bin/env python3
from __future__ import annotations
import json,os,sqlite3
from pathlib import Path
DB=Path(os.environ["SCOREMAX_DB"]).resolve()
TARGET_MSG="msg::PH_SM_QUESTION_WITHDRAWAL_V1::fa07673e47166016f662caac0c6f"
CONTRACT="PH_SM_QUESTION_WITHDRAWAL_V1"
def canon(v): return json.dumps(v,sort_keys=True,separators=(",",":"),default=str)
def main():
    c=sqlite3.connect(DB,timeout=30); c.row_factory=sqlite3.Row
    try:
        tables=[r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
        hits={}
        for t in tables:
            lt=t.lower()
            if not any(k in lt for k in ("diagnostic","auth","transport","receipt","integration")): continue
            cols=[r[1] for r in c.execute(f"PRAGMA table_info({t})").fetchall()]
            rows=[]
            try:
                clauses=[]; args=[]
                for col,val in (("message_id",TARGET_MSG),("contract_name",CONTRACT),("source_system","POWER_HOUSE")):
                    if col in cols: clauses.append(f"{col}=?"); args.append(val)
                if clauses:
                    sql=f"SELECT * FROM {t} WHERE "+" OR ".join(clauses)+" ORDER BY "+("id" if "id" in cols else "rowid")+" DESC LIMIT 30"
                    rows=[dict(r) for r in c.execute(sql,args).fetchall()]
            except Exception as exc:
                rows=[{"error":type(exc).__name__}]
            if rows: hits[t]={"columns":cols,"rows":rows}
        env_names=[]
        # expose names/presence only, never values
        for k in sorted(os.environ):
            ku=k.upper()
            if any(x in ku for x in ("POWER_HOUSE","INTEGRATION","HMAC","TOKEN")):
                v=os.environ.get(k,"")
                env_names.append({"name":k,"present":bool(v),"length":len(v)})
        print("SCOREMAX_SAFE98_WITHDRAWAL_AUTH_DIAG "+canon({
          "message_id":TARGET_MSG,"contract":CONTRACT,"tables":hits,"env":env_names,
          "quick_check":c.execute("PRAGMA quick_check").fetchone()[0],
          "fk":len(c.execute("PRAGMA foreign_key_check").fetchall()),"mutated":False
        }),flush=True)
    finally:c.close()
if __name__=="__main__": main()
