"""Assemble the accepted receiver followed by the isolated scored-SAQ candidate."""
import importlib.util
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def materialize():
    candidate = load('scored_saq_build', REPO / 'ux_vnext_overlay/biology_receiver_20261027/scored_saq_build_v1.py')
    root=REPO/'scoremax_runtime_v669b'
    if root.exists() and candidate.tree(root)==candidate.AFTER_TREE:
        return candidate.apply(root)
    accepted = load('accepted_biology_receiver', REPO / 'scripts/materialize_scoremax_biology_receiver_20261027.py')
    metadata = accepted.materialize()
    return {**metadata, **candidate.apply(REPO / 'scoremax_runtime_v669b')}


if __name__ == '__main__':
    print(json.dumps(materialize(),sort_keys=True))
