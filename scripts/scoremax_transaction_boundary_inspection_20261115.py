"""Source-level transaction review of generated accepted ScoreMax runtime.

Prints source code of critical assessment/Power House paths to Actions log.
It is an inspection, not evidence that signed delivery or grading has passed.
It must never connect to a production database.
"""
from __future__ import annotations
import ast
import json
import sys
from pathlib import Path

REQUIRED={
 "app.py":("submit_assessment_v4","guided_submit_session","process_mastery_result"),
 "scoremax_integration_v1.py":("_activate_release","_withdraw_release",
     "_claim_due","dispatch_due","_dispatch_target",
     "dispatch_release_handoff_ack_once",
     "_envelope","_queue","_receipt","_dispatch_receipt_errors"),
 "scoremax_ph_bridge_v6611d.py":("_withdraw_one","admit_withdrawal_envelope","dispatch_target"),
}
TOKENS=("attempt_answers","mastery_records","marking_status","mastery_evidence_eligible",
        "BEGIN","commit(","rollback(","ACK","acknowledg","withdraw","idempot")
def main(root):
    root=Path(root).resolve()
    if root.name!="scoremax_runtime_v669b" or not (root/"app.py").is_file():
        raise RuntimeError("INSPECT_ACCEPTED_GENERATED_RUNTIME_ONLY")
    report={}
    for filename,names in REQUIRED.items():
        path=root/filename
        if not path.is_file():raise RuntimeError("TRANSACTION_MODULE_MISSING:"+filename)
        source=path.read_text(encoding="utf8")
        functions={n.name:n for n in ast.walk(ast.parse(source))
            if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef))}
        report[filename]={}
        for name in names:
            if name not in functions:raise RuntimeError("TRANSACTION_FUNCTION_MISSING:"+filename+":"+name)
            block=ast.get_source_segment(source,functions[name]) or ""
            present=[k for k in TOKENS if k.casefold() in block.casefold()]
            report[filename][name]={"start_line":functions[name].lineno,
                "end_line":functions[name].end_lineno,"chars":len(block),
                "signals":present}
            print("SCOREMAX_TRANSACTION_SOURCE_BEGIN="+json.dumps({
                "file":filename,"function":name,"source_truncated":len(block)>25000},sort_keys=True),flush=True)
            print(block[:25000],flush=True)
            print("SCOREMAX_TRANSACTION_SOURCE_END="+filename+":"+name,flush=True)
        related=sorted(n for n in functions if any(x in n.casefold()
            for x in ("ack","dispatch","grade","submit","withdraw","mastery","return")))
        report[filename]["related_function_names"]=related[:120]
    print("SCOREMAX_TRANSACTION_SOURCE_AUDIT="+json.dumps({
        "source":"existing_generated_runtime_at_CI_commit",
        "paths":report,
        "direct_production_access":False,
        "actual_write_load_qualified":False,
        "signed_ACK_roundtrip_qualified":False,
        "assessment_idempotency_qualified":False,
        "action":"explicit_review_and_real_disposable_write_test_required"
    },sort_keys=True),flush=True)
if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("USAGE: script <generated_runtime_root>")
    main(sys.argv[1])
