# ScoreMax V6.3.2 Changelog

## Governed chapter identity
- Added chapter catalogue metadata: programme, subject, raw source chapter, chapter number, chapter name, display label, status and metadata source.
- Preserved raw `questions.chapter` as the authoritative filter/evidence identity.
- Added safe source-label parsing without curriculum guessing.
- Added support for governed import columns `Chapter Number` and `Chapter Name`.
- Added consistent chapter presentation to Learn/Subject, Chapter, Practice, My Plan and mastery selection.
- Preserved V6.3.1 Existing Mastery / Potential Mastery graphs unchanged.
- Hardened Practice's dynamic HTML rendering by escaping imported display labels.
- Added a fresh V6.3.2 internal-live database name so V6.3.1 test data is not silently upgraded in place.
