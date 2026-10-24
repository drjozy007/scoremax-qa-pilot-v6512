"""Pin and source-check only this new undeployed storage delta."""
import ast
import difflib
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent
BASE=ROOT/"scoremax_persistent_storage_guard.baseline.py"
TARGET=ROOT/"scoremax_persistent_storage_guard.py"
HELPER=ROOT/"backup_capacity_v1.py"

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def blob(path):
    raw=path.read_bytes()
    return hashlib.sha1(b"blob "+str(len(raw)).encode("ascii")+b"\0"+raw).hexdigest()
assert blob(BASE)=="7a69ed8b1b7d8bd8ba38d1b32875b7d2178d3487"
assert blob(HELPER)=="8c06d8cb61eea5d16330e21f4d45ff23c7b7cfda"
assert sha(HELPER)=="ebb95b113285ae6dd8d3e27eb0c0f537f70eecabd5c728dcae48ef986f4308a3"
old_tree=ast.parse(BASE.read_text(encoding="utf-8"))
new_tree=ast.parse(TARGET.read_text(encoding="utf-8"))
old={n.name:n for n in old_tree.body if isinstance(n,ast.FunctionDef)}
new={n.name:n for n in new_tree.body if isinstance(n,ast.FunctionDef)}
allowed={"check_sqlite","durability_probe","_backup_and_verify","_restore_semantic_check","_qualify_emergency_batches","qualify_database","main"}
changed={name for name in old if ast.dump(old[name])!=ast.dump(new[name])}
assert changed==allowed
old_rows=next(n for n in ast.walk(old["_qualify_emergency_batches"]) if isinstance(n,ast.For) and isinstance(n.target,ast.Name) and n.target.id=="r" and isinstance(n.iter,ast.Name) and n.iter.id=="stored")
new_rows=next(n for n in ast.walk(new["_qualify_emergency_batches"]) if isinstance(n,ast.For) and isinstance(n.target,ast.Name) and n.target.id=="r" and isinstance(n.iter,ast.Name) and n.iter.id=="stored")
assert ast.dump(old_rows)==ast.dump(new_rows)
def release(node):
    return next(n for n in ast.walk(node) if isinstance(n,ast.If) and ast.unparse(n.test)=="release_status == 'NOT_RELEASED'")
assert ast.dump(release(old["_qualify_emergency_batches"]))==ast.dump(release(new["_qualify_emergency_batches"]))
projected={"id","question_id","active","status","review_status","content_environment","scoremax_ready"}
consumed={n.slice.value for n in ast.walk(new["_qualify_emergency_batches"]) if isinstance(n,ast.Subscript) and isinstance(n.value,ast.Name) and n.value.id=="q" and isinstance(n.slice,ast.Constant)}
assert consumed==projected
declarations={"POLICY","APPROVED_REVIEWERS","APPROVED_COVERAGE_PACKAGES","EMERGENCY_RIGHTS"}
def assignments(tree):
    return {n.targets[0].id:ast.dump(n.value) for n in tree.body if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and n.targets[0].id in declarations}
assert assignments(old_tree)==assignments(new_tree)
diff="".join(difflib.unified_diff(BASE.read_text().splitlines(True),TARGET.read_text().splitlines(True),
    fromfile="a/scripts/scoremax_persistent_storage_guard.py",tofile="b/scripts/scoremax_persistent_storage_guard.py"))
(ROOT/"scoremax_persistent_storage_guard.patch").write_text(diff,encoding="utf-8")
receipt={
 "status":"LOCAL_UNDEPLOYED_CANDIDATE_ONLY",
 "scoremax_source":{"repository":"drjozy007/scoremax-qa-pilot-v6512","commit":"096f0c2edaaf1c3360712feca785ec4f06d4cd53",
    "path":"scripts/scoremax_persistent_storage_guard.py","git_blob":blob(BASE),"sha256":sha(BASE)},
 "capacity_helper":{"repository":"drjozy007/power-house-reviewer-service","commit":"4c1b73cbe55ca9756ba532f19a9a872a45432620",
    "path":"runtime_support_v015l9g/backup_capacity_v1.py","git_blob":blob(HELPER),"sha256":sha(HELPER),"bytes":HELPER.stat().st_size,
    "copied_unchanged":True,"active_installed_path":"/opt/powerhouse/app/backup_capacity_v1.py",
    "active_manifest":"../DERIVED_INSTALLED_RUNTIME_20261023.json",
    "namespace_note":"backup_capacity_v1 is not present in the ScoreMax096 tree; package this file beside the guard, whose script directory supplies import precedence.",
    "lock_note":"Existing per-filesystem lock: persistent mount/.powerhouse-capacity.lock; OS-root local fallback uses a filesystem identity under tempfile/powerhouse-capacity. Different backup/intake/job roots on the same filesystem share the lock.",
    "reserve_bytes":536870912,"lock_timeout_seconds":30},
 "candidate_sha256":sha(TARGET),
 "changed_existing_functions":sorted(changed),
 "unchanged_existing_functions":sorted(set(old)-changed),
 "source_checks":{"per_row_academic_validation_ast_unchanged":True,"candidate_and_release_state_validation_ast_unchanged":True,
    "commercial_reviewers_rights_and_policy_constants_unchanged":True,"narrow_question_projection_covers_every_consumed_field":True,
    "question_projection_fields":sorted(projected)},
 "storage_contract":{
    "initial_budget":"max(current database size, owned source snapshot size) * 2 + 4 MiB slack + 512 MiB reserve",
    "progress_budget":"remaining copied pages + full pending restore size (during backup) + 4 MiB slack + 512 MiB reserve",
    "prepublication_budget":"After all restore qualification and the final digest, recheck current free space >= 512 MiB reserve + 4 MiB publication slack under the existing filesystem lock immediately before publish().",
    "copy_bound":"One backup plus one restore, each capped at the admitted source snapshot pages. Pages=256. Private artifacts canonicalized to DELETE journaling.",
    "publication":"Unchanged shared owned_copy_publication verifies target ownership/sidecars, fsyncs the private artifact, and replaces atomically only after backup integrity/FK, persistent restore integrity/FK/counts/reviewers, and streamed digest succeed.",
    "cleanup":"Only this operation's newly created private directory; existing targets, predictable .tmp files, other operation directories, baselines, and source data are not pruned.",
    "handle_ownership":"Every new read/write connection is owned and closed, including partial-open and check failures.",
    "failure_semantics":"Qualification/capacity/controlled publication refusals call existing fail() with SystemExit78 after cleanup. Native sqlite/OSError exceptions still propagate after closing/cleanup. No failure claims successful qualification.",
    "startup_scan":"Only main's earlier duplicate live integrity/FK check is removed. qualify_database performs its existing full live check and semantic/governance checks under one owned read snapshot. Existing later hooks remain unchanged."},
 "delta_test_receipt":"DELTA_TEST_RESULT_20261024.json",
 "limits":[
    "Only tiny synthetic delta tests; execution platform and results are in DELTA_TEST_RESULT_20261024.json. No Render, resource-limit, full-size, startup timing, capacity-allowance, academic-content or launch qualification.",
    "Shared helper's Render contract requires the real /data mount and defaults POWER_HOUSE_REVIEW_SERVICE_DATA_DIR to /data. A different mount/environment fails closed until separately reviewed; no reserve has been lowered.",
    "Filesystem lock coordinates participating shared-helper copies only. Unrelated writers/native ScoreMax630 backups do not automatically join it; live/WAL growth and external disk users can still cause a bounded progress refusal.",
    "The final reserve check cannot prevent an unrelated writer from consuming disk after that check; it is a current admission check, not a cross-process storage quota.",
    "One read snapshot can pin WAL while qualification and recovery verification run; this does not establish a live-concurrency resource guarantee.",
    "Process termination may leave its private directory. This patch never guesses ownership and deletes old/orphan directories; those files count against admission and need an authorized lifecycle policy.",
    "Restore semantic assertions preserve the existing five table counts plus reviewer state; this is not a new full relational identity or academic qualification.",
    "ScoreMax630 pilot_readiness_engine.sqlite_backup and all other native assembled backup paths remain unchanged. This guard delta is not a complete native-runtime storage correction.",
    "The helper file must be packaged beside the modified guard; no remote packaging or branch has been changed."
 ],
 "production_access":False,"services_started":0,"historical_accepted_suites_replayed":0,"remote_changes":False
}
(ROOT/"CANDIDATE_REVIEW_20261024.json").write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"passed":True,"candidate_sha256":receipt["candidate_sha256"],"helper_sha256":sha(HELPER),"changed_functions":len(changed),"per_row_and_release_ast_unchanged":True}))
