"""Construct and qualify a shadow view ONLY on a disposable ScoreMax DB.

Not invoked by production, boot, release dispatch, Render or learner actions.
Output is test evidence, not academic release authority.
"""
from __future__ import annotations
import json
from pathlib import Path
import sqlite3
import sys
from scoremax_persistent_shadow_visibility_candidate_20261115 import (
    install,rebuild,read,native_rows,native_scope,native_live,PROGRAMMES)
def main(root,db):
    root=root.resolve();db=db.resolve()
    if not db.is_file() or db.is_symlink() or not str(db).startswith("/tmp/"):
        raise RuntimeError("SHADOW_DISPOSABLE_PATH_REQUIRED")
    if not (root/"app.py").is_file():
        raise RuntimeError("SHADOW_ACCEPTED_RUNTIME_MISSING")
    sys.path.insert(0,str(root))
    import question_contract_engine as contracts
    with sqlite3.connect(db) as c:
        c.row_factory=sqlite3.Row
        c.create_function("scoremax_release_programme",2,contracts.programme_for_release,deterministic=True)
        if c.execute("PRAGMA quick_check").fetchone()[0]!="ok":
            raise RuntimeError("SHADOW_SOURCE_INTEGRITY_FAILED")
        protected=(
            "questions","attempts","attempt_answers","mastery_records",
            "integration_ph_content_releases","integration_ph_release_question_membership",
            "integration_ph_product_activation_authorizations",
            "ph_bridge_staged_withdrawal_exclusions_v6611e")
        before={t:c.execute("SELECT COUNT(*) FROM "+t).fetchone()[0] for t in protected}
        triggers=install(c)
        scope=native_scope(root);live=native_live(root)
        record=rebuild(c,scope,contracts.programme_aliases,live)
        for programme in PROGRAMMES:
            origin,rows=read(c,programme,scope,contracts.programme_aliases,live)
            if origin!="SHADOW" or rows!=native_rows(c,programme,scope,contracts.programme_aliases,live):
                raise RuntimeError("SHADOW_PRODUCTION_SHAPED_PARITY_FAILED:"+programme)
        after={t:c.execute("SELECT COUNT(*) FROM "+t).fetchone()[0] for t in protected}
        if after!=before:raise RuntimeError("SHADOW_ALTERED_PROTECTED_ROWS")
        if c.execute("PRAGMA quick_check").fetchone()[0]!="ok":
            raise RuntimeError("SHADOW_POST_INTEGRITY_FAILED")
        print("SCOREMAX_DISPOSABLE_SHADOW_PREPARED="+json.dumps({
            "rebuild_ms":record["rebuild_ms"],"programme_counts":record["sizes"],
            "authority_source_tables":7,"invalidation_triggers":triggers,
            "protected_census_unchanged":True,"quick_check":"ok",
            "real_ph_content_qualified":False,"production_db_touched":False,
            "live_runtime_enabled":False
        },sort_keys=True),flush=True)
if __name__=="__main__":
    if len(sys.argv)!=3:raise SystemExit("Usage: script runtime_root disposable_db")
    main(Path(sys.argv[1]),Path(sys.argv[2]))
