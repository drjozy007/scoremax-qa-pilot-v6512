"""Build-time bounded reuse for the existing pure programme resolver."""
from pathlib import Path
import hashlib

BEFORE_SHA256 = '227ce744fe5b843d15d97593058a3e5ae4daa6a9acf0c7bb2f6bcbf2dc1fba33'
AFTER_SHA256 = 'd81929f6c366d3a55f72cac3b83facf416e3d4a679e13cb9326389078baf3a72'
RUNTIME_PATCH = "\n# SCOREMAX_PURE_PROGRAMME_RESOLUTION_CACHE_20261121\ndef _install_programme_resolution_cache_20261121():\n    \"\"\"Reuse only pure source-scope interpretation, never live release eligibility.\"\"\"\n    from functools import lru_cache, wraps\n\n    source_resolver = programme_for_release\n\n    @lru_cache(maxsize=128)\n    def cached(release_programme, curriculum_json):\n        return source_resolver(release_programme, curriculum_json)\n\n    @wraps(source_resolver)\n    def resolve(release_programme, curriculum_json):\n        # Keep compatibility and fail-closed handling for non-string/malformed input.\n        # Bounds cap retained source text; oversized input follows the same resolver.\n        if (type(release_programme) is str and type(curriculum_json) is str\n                and len(release_programme) <= 256 and len(curriculum_json) <= 4096):\n            return cached(release_programme, curriculum_json)\n        return source_resolver(release_programme, curriculum_json)\n\n    resolve.cache_info = cached.cache_info\n    resolve.cache_clear = cached.cache_clear\n    globals()['programme_for_release'] = resolve\n\n\n_install_programme_resolution_cache_20261121()\n"

def apply(root):
    path = Path(root) / 'question_contract_engine.py'
    original = path.read_bytes()
    checksum = hashlib.sha256(original).hexdigest()
    if checksum == AFTER_SHA256:
        return {'replayed': True}
    if checksum != BEFORE_SHA256:
        raise ValueError('PROGRAMME_RESOLVER_CACHE_SOURCE_DRIFT')
    candidate = original.decode('utf8') + RUNTIME_PATCH
    compile(candidate, str(path), 'exec')
    if hashlib.sha256(candidate.encode('utf8')).hexdigest() != AFTER_SHA256:
        raise ValueError('PROGRAMME_RESOLVER_CACHE_CANDIDATE_MISMATCH')
    path.write_text(candidate, encoding='utf8', newline='\n')
    return {'pure_programme_resolution_cache': True, 'cache_maxsize': 128,
            'release_eligibility_cached': False, 'database_changes': False}

