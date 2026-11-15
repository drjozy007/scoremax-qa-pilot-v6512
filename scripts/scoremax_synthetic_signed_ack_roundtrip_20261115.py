"""Signed Power House ACK dispatcher roundtrip against an isolated fake HTTPS peer.

Exercises EXISTING ScoreMax envelope, queue, claim, signer, receipt-validation,
retry and delivery-state code. The peer is a local mock, never a real endpoint.
This DOES NOT qualify real Power House receipt data or network delivery.
"""
from __future__ import annotations
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from unittest.mock import patch

def main(runtime):
    runtime=Path(runtime).resolve()
    if runtime.name!="scoremax_runtime_v669b" or not (runtime/"scoremax_production.py").is_file():
        raise RuntimeError("ACCEPTED_SCOREMAX_RUNTIME_REQUIRED")
    with tempfile.TemporaryDirectory(prefix="scoremax-signed-ack-") as tmp:
        root=Path(tmp)
        for directory in ("state","backup","intake"):(root/directory).mkdir()
        os.environ.update({
            "SCOREMAX_ENV":"production",
            "SCOREMAX_SECRET":"test-only-signed-ack-session-secret-long-string",
            "SCOREMAX_STAGING_SESSION_SECRET":"test-only-staging-session-secret-long-string",
            "SCOREMAX_BOOTSTRAP_ADMIN_PASSWORD":"synthetic-only-admin",
            "SCOREMAX_BOOTSTRAP_ADMIN_EMAIL":"synthetic-admin@scoremax.invalid",
            "SCOREMAX_DB":str(root/"state"/"scoremax.db"),
            "SCOREMAX_PERSISTENT_ROOT":str(root),
            "SCOREMAX_BACKUP_DIR":str(root/"backup"),
            "SCOREMAX_CONTENT_INTAKE_DIR":str(root/"intake"),
            "SCOREMAX_INSTANCE_COUNT":"1","WEB_CONCURRENCY":"1",
            "SCOREMAX_PUBLIC_BASE_URL":"https://localhost",
            "SCOREMAX_POWER_HOUSE_BASE_URL":"https://powerhouse.invalid",
            "SCOREMAX_SMTP_HOST":"smtp.invalid","SCOREMAX_SMTP_FROM":"test@scoremax.invalid",
            "SCOREMAX_SEND_EMAIL_VERIFICATION":"0","SCOREMAX_REQUIRE_EMAIL_VERIFICATION":"0",
            "SCOREMAX_PUBLIC_STUDENT_OPENING":"0",
            "SCOREMAX_ENFORCE_PAYWALL":"0",
        })
        sys.path.insert(0,str(runtime))
        import scoremax_production
        from scoremax_ph_bridge_v6611d import WITHDRAWAL_ACK, RELEASE
        sm=scoremax_production.scoremax
        i=sm.integration_v1
        c=sm.db()
        try:
            payload={
                "export_public_id":"SYNTHETIC-EXPORT-001",
                "population_sha256":"a"*64,
                "items":[],
                "historical_attempts_preserved":True,
                "scoremax_release":RELEASE,
                "release_authority_conferred":False,
            }
            env=i._envelope(WITHDRAWAL_ACK,"POWER_HOUSE",
                "synthetic-withdrawal-idem","SYNTHETIC-EXPORT-001",
                payload,RELEASE,"INTERNAL")
            idempotency_key=env["idempotency_key"]
            _=i._queue(c,env,"SYNTHETIC-EXPORT-001",
                      "PH_WITHDRAWAL_EXPORT","SYNTHETIC-EXPORT-001")
            c.commit()
            queued=c.execute("""SELECT * FROM integration_outbox
                WHERE contract_name=? AND idempotency_key=?""",
                (WITHDRAWAL_ACK,idempotency_key)).fetchone()
            if queued is None:raise RuntimeError("SIGNED_ACK_NOT_QUEUED")
            same=i._queue(c,env,"SYNTHETIC-EXPORT-001",
                      "PH_WITHDRAWAL_EXPORT","SYNTHETIC-EXPORT-001")
            c.commit()
            if same!=env["message_id"]:
                raise RuntimeError("ACK_QUEUE_IDEMPOTENCY_BROKEN")
            if c.execute("""SELECT COUNT(*) FROM integration_outbox
                WHERE contract_name=? AND idempotency_key=?""",
                (WITHDRAWAL_ACK,idempotency_key)).fetchone()[0]!=1:
                raise RuntimeError("ACK_QUEUE_DUPLICATED")
            url,path,direction=i._dispatch_target(WITHDRAWAL_ACK)
            if not url.startswith("https://") or direction!="SCOREMAX_TO_POWER_HOUSE" or "question-withdrawal-acks" not in path:
                raise RuntimeError("WITHDRAWAL_ACK_DISPATCH_ROUTE_NOT_PATCHED")
            receipt={
                "receipt_id":"RCPT::POWER_HOUSE::SYNTHETIC",
                "message_id":env["message_id"],
                "contract_name":env["contract_name"],
                "receiver_system":"POWER_HOUSE",
                "received_at":i.utcnow(),
                "status":"ACCEPTED",
                "duplicate_of_receipt_id":None,
                "accepted_schema_version":env["schema_version"],
                "payload_checksum_sha256":env["payload_checksum_sha256"],
                "errors":[],
            }
            if i._dispatch_receipt_errors(receipt,env):
                raise RuntimeError("SYNTHETIC_PEER_RECEIPT_INVALID")
            calls=[]
            class FakeResponse:
                status=202
                def read(self):return i.canonical_json(receipt).encode()
            def fake_urlopen(request,timeout):
                if request.full_url!=url:raise RuntimeError("UNEXPECTED_PEER_URL")
                body=json.loads(request.data)
                headers={k.lower():v for k,v in request.header_items()}
                sent=headers["x-sent-at"];signature=headers["x-signature"]
                expected="hmac-sha256="+i.signature("POST",path,
                    body["message_id"],sent,body["payload_checksum_sha256"],
                    "synthetic-HMAC-secret")
                if signature!=expected:raise RuntimeError("OUTGOING_SIGNATURE_MISMATCH")
                if headers["authorization"]!="Bearer synthetic-bearer":
                    raise RuntimeError("OUTGOING_BEARER_MISMATCH")
                calls.append((body["message_id"],sent))
                return FakeResponse()
            with patch.object(i,"_credentials",return_value=[(
                "synthetic-bearer","synthetic-HMAC-secret")]), patch.object(
                i.urlrequest,"urlopen",side_effect=fake_urlopen):
                first=i.dispatch_due(c,limit=1,outbox_ids=[queued["id"]])
                second=i.dispatch_due(c,limit=1,outbox_ids=[queued["id"]])
            if first["delivered"]!=1 or second["attempted"]!=0 or len(calls)!=1:
                raise RuntimeError("SIGNED_ACK_DELIVERY_NOT_IDEMPOTENT:"+str((first,second,len(calls))))
            actual=c.execute("SELECT status,receipt_json,attempt_count FROM integration_outbox WHERE id=?",
                (queued["id"],)).fetchone()
            if actual["status"]!="DELIVERED" or int(actual["attempt_count"])!=1:
                raise RuntimeError("OUTBOX_TERMINAL_STATUS_DRIFT")
            stored=json.loads(actual["receipt_json"])
            if stored["message_id"]!=env["message_id"]:
                raise RuntimeError("RECEIPT_IDENTITY_NOT_PRESERVED")
            if c.execute("PRAGMA integrity_check").fetchone()[0]!="ok":
                raise RuntimeError("ACK_DISPOSABLE_INTEGRITY_FAILURE")
            print("SCOREMAX_SYNTHETIC_SIGNED_ACK_CONTRACT_PASS="+json.dumps({
                "source":"accepted_scoremax_dispatcher",
                "contract":WITHDRAWAL_ACK,
                "queued_unique":True,"signed_bearer_and_hmac_verified":True,
                "fake_peer_receipt_validated":True,
                "outbox_delivered_once":True,
                "terminal_retry_blocked":True,
                "peer":"strict_mock_no_network",
                "live_power_house_receipt":False,
                "production_touched":False,
            },sort_keys=True),flush=True)
        finally:c.close()
if __name__=="__main__":
    if len(sys.argv)!=2:raise SystemExit("USAGE: script <generated runtime>")
    main(sys.argv[1])
