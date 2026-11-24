"""Cross-platform package check for the sealed V17 display-only continuation."""
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    manifest_path = ROOT / 'evidence/SCOREMAX_PRACTICE_LABEL_CANDIDATE_20261124_V17.json'
    raw = manifest_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != '76bec88d914c5c9db0a1d44ce81499df29f3b183b776f2ebea972c6e80d21ee8':
        raise ValueError('EXACT_FROZEN_V17_MANIFEST_REQUIRED')
    manifest = json.loads(raw)
    for relative, expected in manifest['files'].items():
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != expected:
            raise ValueError('FROZEN_V17_SOURCE_DRIFT:' + relative)
    builder = ROOT / 'ux_vnext_overlay/biology_receiver_20261027/practice_label_build_20261124_v17.py'
    spec = importlib.util.spec_from_file_location('frozen_v17_package', builder)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    runtime = ROOT / 'scoremax_runtime_v669b'
    if module.tree(runtime) != manifest['candidate_runtime_tree_sha256']:
        raise ValueError('EXACT_V17_RUNTIME_REQUIRED')
    from jinja2 import Environment
    text = (runtime / 'templates/test_setup.html').read_text(encoding='utf8')
    Environment().parse(text)
    old = (ROOT / 'qualification/reference_v13/templates/test_setup.html').read_text(encoding='utf8')
    if old.count('Scored practice') != 2 or text != old.replace('Scored practice', 'Practice'):
        raise ValueError('ONLY_TWO_VISIBLE_LABEL_CHANGES_REQUIRED')
    if '<option value="SCORED">Practice</option>' not in text:
        raise ValueError('EXISTING_RESPONSE_MODE_REQUIRED')
    print('SM_V17_TEMPLATE_AND_UNCHANGED_RESPONSE_MODES_PASSED')


if __name__ == '__main__':
    main()
