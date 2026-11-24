# V11 native chapter count cost

A hosted mixed run exposed p95 1780.255294 ms against the unchanged 1500-ms gate on one CPU, one worker/four threads and no extra indexes. Display-cache commit invalidation is correct and retained. Profiling found repeated scans of the same visible legacy inventory for each chapter.

V11 groups legacy rows by their exact binary chapter value after the existing native programme/live filters, carrying a multiplicity. It retains every PH row with its exact internal ID and opaque version/checksum. The original full native chapter predicates run unchanged over that smaller current statement, summing multiplicities. This optimization is enabled only for the exact pinned native SQL emitter and exact known column set; unknown functions/fields use the former query. Only code identity is memoized, never authority or learner data.

No schema, resources, indexes, marking rules, source weights, commit invalidation or formal-credit checks change. The V11 materializer composes the sealed V10 builder and one checked ux_student_batch.py delta. V9 and V10 builders remain unchanged. Production deployment and actual Render capacity are separate from software qualification.
