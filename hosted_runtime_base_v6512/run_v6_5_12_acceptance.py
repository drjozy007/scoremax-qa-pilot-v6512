"""ScoreMax V6.5.12 full acceptance runner.

Requires the normal ScoreMax runtime dependencies from requirements.txt. It preserves the
V6.5.10 accepted integration runner, then adds V6.5.11 pilot and V6.5.12 systemic
rectification gates. Use only a disposable database/test environment.
"""
from __future__ import annotations
import os, secrets, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run(path: str) -> None:
    env = os.environ.copy()
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['SCOREMAX_ENV'] = 'test'
    env.setdefault('SCOREMAX_BOOTSTRAP_ADMIN_PASSWORD', secrets.token_urlsafe(24))
    p = subprocess.run([sys.executable, str(ROOT / path)], cwd=ROOT, text=True, capture_output=True, env=env)
    print(f"\n=== {path} ===")
    print(p.stdout.rstrip())
    if p.returncode:
        print(p.stderr, file=sys.stderr)
        raise SystemExit(p.returncode)


def main() -> None:
    run('run_v6_5_10_acceptance.py')
    run('tests/test_v6_5_11_synthetic_learner_contract.py')
    run('tests/test_v6_5_12_synthetic_isolation_rectification.py')
    print('\nSCOREMAX V6.5.12 FULL LOCAL ACCEPTANCE PASS')
    print('Pilot scope remains exactly one deterministic + one visual-semantic qa_student.')
    print('Growth Engine unchanged. Integration protocol release remains 6.5.10.')


if __name__ == '__main__':
    main()
