# Prepared invitation-only pilot delta — 25 October 2026

Status: PREPARED, NOT DEPLOYED; NO-GO for student question activation.

The live ScoreMax commit remains 6302547c0543057c249b60b65e3348a52d9f6a27. This preparation adds a private 1–20 student allowlist, closes student self-registration in pilot mode, retains native CSRF/session/role/release checks, blocks formal mastery creation and in-flight mastery submission, labels pilot practice feedback, and labels unavailable chapters Coming soon. It creates no credentials, accounts, question packages or release authority.

Configuration proposal: SCOREMAX_INVITE_ONLY_PILOT=1 and SCOREMAX_PILOT_STUDENT_IDS_JSON set privately to the owner-approved existing verified student account IDs. No real identifiers are committed. The selected owner tester remains private. No further real students have been invited.

The normal deploy_ux_vnext.py is deliberately unchanged on this preparation branch: changing it would automatically repeat an already completed native-backup qualifier. deploy_ux_vnext.proposed.py contains the exact appended installer hook for review; it must replace the normal builder only in a later explicitly admitted candidate transition. No checks were removed or disabled. No PR or workflow was opened/dispatched.

Local validation: eight focused Flask boundary tests passed in 0.345 seconds using Flask 3.1.3/Werkzeug 3.1.6 on Python 3.12 Windows. Exact hash-pinned source assembly reproduced the accepted 260-file backup runtime e18573635e90ad3149bafd4ece5b74ea68e0a6d48e29e2222e71400fbd9d7b3c, then changed only scoremax_production.py, invite_only_pilot_runtime.py and templates/ux_subject_chapters.html. Candidate: 261 files, runtime SHA-256 b9b7fcb111dc45d41f9c18683aaaa39bf23ad9c4dba988c88c38bb0e27a7351b. Installer replay was byte-identical. Both unavailable/available chapter rendering cases passed. This is neither Linux/deployment acceptance nor a native scoring or production workload qualification.

No production deployment, restart, question import, product activation or paid infrastructure occurred. Normal owner sign-in and programme selection did update their ordinary student session/preference. Read-only operator SQL performed zero writes. One reversible clean-cache hint on a completed Power House managed backup changed zero file bytes and recorded zero new memory events. Historical production memory failures remain failed.

Final blockers and the exact two staged release identities are recorded in the existing Power House launch-gate handoff. The 291-question proposal is a separate pilot release choice, not a replacement of the frozen Gate D 393-question workload.
