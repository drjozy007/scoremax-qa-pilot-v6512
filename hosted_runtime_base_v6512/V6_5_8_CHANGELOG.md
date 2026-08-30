# V6.5.8 Changelog

## Production changes
- `app.py`: release identity advanced to 6.5.8; successful recall/reconfirmation now preserves an already recovered learning area when the targeted attempt has >=3 answered items and >=80% score.
- `scoremax_integration_v1.py`: `SM_PH_DELIVERY_EVIDENCE_V1` now derives recovery/reconfirmation attempt/success counters from immutable pinned attempt evidence; suppressed aggregates emit zero counters.

## Tests/evidence
- Added permanent learner/evidence regression covering the mandated Weak Area → Recovery → recall journey, failed-later-recall behaviour, immutable evidence counting, and minimum-N privacy suppression.
- Existing descendant-version assertions widened to admit 6.5.8 without changing behavioural expectations.
