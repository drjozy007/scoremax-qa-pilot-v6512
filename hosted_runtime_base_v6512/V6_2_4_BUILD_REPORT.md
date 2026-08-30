# ScoreMax V6.2.4 Build Report

## Release
**Curriculum Isolation & Accessibility Foundations**

Built from the independently reviewed V6.2.3 baseline. No database migration is required.

## Release-blocking correctness fix
The unconditional final query in `_curriculum_chapters()` was removed. A learner whose programme has no matching content now receives no chapters rather than every live chapter across every programme.

Current-study subject availability, chapter lists and attempt-derived accuracy are also scoped to conservative exact programme/qualification aliases. Future pathways remain visible through Pathway Explorer rather than leaking into current study.

An empty bank now produces unknown coverage (`NULL`/`None`), not a false 0% coverage signal.

## Code hygiene
Removed the unused four-level mastery-order dictionary that omitted Advanced and Expert. The live six-level ladder remains Foundation, Exam Ready, Advanced, Distinction, Expert and Elite.

## Accessibility foundations
- skip-to-main-content link;
- focusable main landmark;
- tabs with `tablist`, `tab`, `tabpanel`, `aria-controls`, `aria-labelledby` and roving tabindex;
- ArrowLeft, ArrowRight, Home and End keyboard navigation;
- visible `:focus-visible` indicators;
- reduced-motion support;
- mobile-menu Escape close, focus containment and focus return.

## Verification
The clean packaged release passed 233 automated checks:

- V5.5: 52
- V6.0: 34
- V6.1: 41
- V6.2: 30
- V6.2.1: 10
- V6.2.2: 19
- V6.2.3: 33
- V6.2.4: 14

Python compilation, package checksum-manifest validation and SQLite preservation/integrity checks also passed.

## Honest boundary
Markup and JavaScript regression checks cannot prove screen-reader quality or visual usability. A live keyboard, 200% zoom, NVDA/VoiceOver and mobile acceptance pass remains required before public pilot use.
