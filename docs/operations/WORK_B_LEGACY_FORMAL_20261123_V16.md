# Fresh current legacy formal-evidence aggregation V16

Large legacy learner histories repeatedly constructed row dictionaries solely to
prove that current question keys still exist and are not owned by Power House.
The existing operation savepoint now makes that proof with bounded fresh SQL
aggregates. Only an entirely legacy batch may return through this path.

Exact Power House identity, membership, release, withdrawal and activation
authority follow the unchanged native path. Missing, ambiguous and marked PH
records retain the original fallback and error behavior. No persistent cache,
schema migration, index, mastery rule, assessment weight or worker change is made.

The build accepts only the exact V13 runtime and changes only
`ph_mastery_evidence.py`; drift fails before writes. Differential SQLite tests use
the pinned V13 source, real external commits, current writer changes, opaque
metadata, native collation and 300/1500-key batches. Existing signed native
submission and image/withdrawal/recovery gates remain required.

Production remains one worker with four threads. The strict capacity target is
p95 below1500ms, including the zero-extra-index mixed workload. Previous failed
hosted measurements remain evidence; local and software results do not imply
production readiness or assessed AI marking acceptance.
