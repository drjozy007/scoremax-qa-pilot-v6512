"""Run current navigation checks and the applicable finite Render recovery checks.

The superseded /proc prototype remains an immutable fixture provider. Its
current replacement inherits every archive test and adds native SQLite locking
controls. That archive action targets the existing Linux Render disk; Windows
application acceptance does not execute or claim that deployment-only action.
"""
import json
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
HISTORICAL_FIXTURE = 'test_lossless_headroom_recovery_v1'
RENDER_ARCHIVE = 'test_lossless_headroom_recovery_v2'


def leaves(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from leaves(item)
        else:
            yield item


def select_current(suite, platform):
    selected, exclusions = [], []
    for test in leaves(suite):
        module = type(test).__module__
        reason = None
        if module == HISTORICAL_FIXTURE:
            reason = 'SUPERSEDED_PROC_PROTOTYPE_FIXTURES_INHERITED_BY_CURRENT_V2'
        elif module == RENDER_ARCHIVE and platform != 'posix':
            reason = 'N_A_WINDOWS_EXISTING_LINUX_RENDER_ONLY_ARCHIVE_ACTION'
        if reason:
            exclusions.append({'test': test.id(), 'reason': reason})
        else:
            selected.append(test)
    return unittest.TestSuite(selected), exclusions


def main():
    discovered = unittest.defaultTestLoader.discover(
        str(ROOT / 'tests/navigation_current_20261123'), pattern='test_*.py')
    suite, exclusions = select_current(discovered, os.name)
    inventory = {'platform': os.name, 'selected_tests': suite.countTestCases(),
                 'explicit_historical_or_platform_scope': exclusions,
                 'application_test_exclusions': 0,
                 'render_recovery_required_on_linux': os.name == 'posix'}
    output = ROOT / 'qualification/current_navigation_test_selection_v2.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(inventory, sort_keys=True, indent=2), encoding='utf8')
    print(json.dumps(inventory, sort_keys=True), flush=True)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(main())
