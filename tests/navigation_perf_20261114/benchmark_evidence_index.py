"""Synthetic CPU microbenchmark of the exact repeated evidence list filters.

Not an end-to-end HTTP timing. Reproduces the existing per-subject/per-chapter
iteration pattern at controlled input sizes. No production data or credentials.
"""
from collections import defaultdict
from statistics import median
from time import perf_counter
import random
import json

def run_case(subjects=4, chapters=12, events=40000, repeats=5):
    rng=random.Random(20261114)
    labels=[f"Subject {s}" for s in range(subjects)]
    chapter_ids=[f"Chapter {c}" for c in range(chapters)]
    evidence=[{"subject":labels[rng.randrange(subjects)],"chapter":chapter_ids[rng.randrange(chapters)],"value":rng.randrange(2)} for _ in range(events)]

    def baseline():
        result=[]
        for subject in labels:
            result.append((subject,"ALL",sum(x["value"] for x in evidence if x["subject"].casefold()==subject.casefold())))
            for ch in chapter_ids:
                result.append((subject,ch,sum(x["value"] for x in evidence if x["subject"].casefold()==subject.casefold() and x["chapter"]==ch)))
        return result

    def optimized():
        by_subject=defaultdict(list);by_chapter=defaultdict(list)
        for row in evidence:
            key=row["subject"].casefold()
            by_subject[key].append(row)
            by_chapter[(key,row["chapter"])].append(row)
        result=[]
        for subject in labels:
            result.append((subject,"ALL",sum(x["value"] for x in by_subject[subject.casefold()])))
            for ch in chapter_ids:
                result.append((subject,ch,sum(x["value"] for x in by_chapter[(subject.casefold(),ch)])))
        return result

    assert baseline()==optimized(), "EVIDENCE_AGGREGATION_NOT_EQUIVALENT"
    durations={}
    for name,fn in (("baseline",baseline),("optimized",optimized)):
        observations=[]
        for _ in range(repeats):
            start=perf_counter();fn();observations.append((perf_counter()-start)*1000)
        durations[name]=round(median(observations),3)
    return {"subjects":subjects,"chapters_per_subject":chapters,"evidence_records":events,
            "runs":repeats,"baseline_median_ms":durations["baseline"],"candidate_median_ms":durations["optimized"],
            "speedup":round(durations["baseline"]/durations["optimized"],2) if durations["optimized"] else None,
            "scope":"synthetic evidence-index CPU microbenchmark only; not page/server response"}

if __name__=="__main__":
    print("SCOREMAX_EVIDENCE_MICROBENCH="+json.dumps(run_case(),sort_keys=True))
