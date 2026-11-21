"""Read-only shared transactional database cutover preflight.

This is an executable contract inventory against ScoreMax's GENERATED ACCEPTED
runtime, not a PostgreSQL adapter, schema migration or deployment.
Fail closed on source drift. Never opens live databases or network connections.
"""
from __future__ import annotations
import ast
import hashlib
import json
from pathlib import Path
import re
import sys

SOURCE_FILES=("app.py","scoremax_integration_v1.py","scoremax_ph_bridge_v6611d.py",
              "ph_mastery_evidence.py")
CRITICAL_FUNCTIONS={
 "app.py":("db","submit_assessment_v4","process_mastery_result",
           "learner_answer_evidence","_programme_scope_sql","live_question_clause"),
 "scoremax_integration_v1.py":("_activate_release","_withdraw_release","_claim_due"),
 "scoremax_ph_bridge_v6611d.py":("_withdraw_one",),
}
DB_DIFFERENCES={
 "sqlite_connection_and_uri":r"\bsqlite3\.(?:connect|Connection|Row)\b",
 "exclusive_writer_claim":r"\bBEGIN IMMEDIATE\b",
 "sqlite_schema_introspection":r"\bPRAGMA\b",
 "sqlite_dialect_insert":r"\bINSERT\s+OR\s+(?:IGNORE|REPLACE|ABORT)\b",
 "sqlite_conflict_syntax":r"\bON\s+CONFLICT\b",
 "sqlite_lastrowid":r"\blastrowid\b",
 "sqlite_auto_increment":r"\bAUTOINCREMENT\b",
 "sqlite_udf":r"\bcreate_function\s*\(",
 "sqlite_sql_lower":r"\blower\s*\(",
 "sqlite_null_datetime":r"\b(?:datetime|strftime|julianday)\s*\(",
 "sqlite_sql_parameters":r"\?",
}
REQUIRED_SAFETY={
 "app.py":{
   "submit_assessment_v4":("BEGIN IMMEDIATE","assessment_sessions",
      "submitted_attempt_id","attempt_answers","mastery_evidence_eligible",
      "process_mastery_result","c.commit()","c.rollback()"),
   "process_mastery_result":("mastery_form_results","mastery_records",
      "effective_mastery_status","question_ids_have_formal_evidence"),
   "_programme_scope_sql":("integration_ph_content_releases",
      "integration_ph_question_version_store",
      "integration_ph_release_question_membership",
      "integration_ph_product_activation_authorizations",
      "ph_bridge_staged_withdrawal_exclusions_v6611e"),
 },
 "scoremax_integration_v1.py":{
   "_withdraw_release":("WITHDRAWN","_preserve_other_active_memberships"),
   "_claim_due":("integration_outbox",),
 },
}
POSTGRES_PROOF_REQUIRED=(
 "same transaction atomic idempotency claim plus unique assessment_session identity",
 "commit attempt, frozen answers, evidence, mastery and session state atomically",
 "snapshot-isolated signed PH admission and authorisation withdrawal with ACK outbox",
 "legacy and PH version/checksum + family + programme + zero-weight exclusion parity",
 "functional equivalence of SQLite lower/trim/NULL/strftime/json and all registered UDF",
 "transaction-safe outbox lease/claim with concurrent distinct workers",
 "stable opaque IDs and exact answer/history/version preservation during transfer",
 "cross-database consistency without distributed commit or silent dual-authority window",
 "reversible cutover with frozen writes, backup, restore, replay and exact-row checks",
 "50 concurrency p95 <1500ms plus mixed writes no lost/duplicate credit",
)

def main(root:Path):
    root=Path(root).resolve()
    if root.name!="scoremax_runtime_v669b" or not (root/"app.py").is_file():
        raise RuntimeError("ACCEPTED_SCOREMAX_RUNTIME_REQUIRED")
    report={}
    source_total=0
    for file in SOURCE_FILES:
        p=root/file
        if not p.is_file():raise RuntimeError("MISSING_MIGRATION_SOURCE:"+file)
        src=p.read_text(encoding="utf8")
        parsed=ast.parse(src)
        fns={}
        for node in parsed.body:
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
                fns.setdefault(node.name,[]).append(node)
        entries={}
        for fn in CRITICAL_FUNCTIONS.get(file,()):
            if fn not in fns:raise RuntimeError("CRITICAL_MIGRATION_HANDLER_ABSENT:"+file+":"+fn)
            # Some functions are intentionally wrapped later. Inspect ALL
            # definitions rather than arbitrarily choosing the earlier one.
            snippets=[ast.get_source_segment(src,node) or "" for node in fns[fn]]
            joined="\n".join(snippets)
            missing=[marker for marker in REQUIRED_SAFETY.get(file,{}).get(fn,())
                     if marker not in joined]
            if missing:raise RuntimeError(
                "ORIGINAL_ACADEMIC_CONTRACT_DRIFT:"+file+":"+fn+":"+repr(missing))
            entries[fn]={"definitions":len(snippets),
                         "line_ranges":[(node.lineno,node.end_lineno) for node in fns[fn]],
                         "sha256":hashlib.sha256(joined.encode()).hexdigest()[:16]}
        counts={name:len(re.findall(pattern,src,re.I))
                for name,pattern in DB_DIFFERENCES.items()}
        report[file]={"source_lines":src.count("\n")+1,
           "dialect_occurrences":counts,"critical_functions":entries}
        source_total+=len(src)
    # The current app advertises no PostgreSQL transactional connector.
    # Never interpret a research-only adapter or design as completed migration.
    print("SCOREMAX_SHARED_DATABASE_PRECHECK="+json.dumps({
       "source":"generated_accepted_runtime_only",
       "architecture":"SQLite_single_persistent_disk_Gunicorn",
       "code_bytes_examined":source_total,
       "dialect_inventory":report,
       "required_acceptance_contracts":POSTGRES_PROOF_REQUIRED,
       "provisioned_postgresql":False,
       "cross_backend_tests_executed":False,
       "production_database_copied":False,
       "shared_db_cutover_qualified":False,
       "multi_instance_routing_authorised":False,
       "result":"NOT_READY_FAIL_CLOSED",
    },sort_keys=True),flush=True)

if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("USAGE: script <generated_runtime_root>")
    main(Path(sys.argv[1]))
