"""ScoreMax release-identity compatibility helpers.

Acceptance suites use this instead of hard-coded descendant allowlists. A current
release is a compatible descendant only when it stays within the same major release
and is not older than the governed baseline being asserted. Functional assertions
still prove the actual preserved behaviour.
"""
from __future__ import annotations
import re

_RELEASE_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")

def release_tuple(value: str) -> tuple[int, int, int]:
    match = _RELEASE_RE.fullmatch(str(value or "").strip())
    if not match:
        raise ValueError(f"Invalid ScoreMax release version: {value!r}")
    return tuple(int(part) for part in match.groups())

def is_compatible_descendant(current: str, baseline: str) -> bool:
    cur = release_tuple(current)
    base = release_tuple(baseline)
    return cur[0] == base[0] and cur >= base
