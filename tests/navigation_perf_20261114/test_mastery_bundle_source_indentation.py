"""Protect source-derived Python indentation for chapter-mastery read-bundle patches.

This focused test runs before the costly 100,800-question benchmark. Repeated
installer indentation failures must be addressed architecturally, not patched
one source-line position at a time.
"""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[2]
PATH=ROOT/"scripts"/"scoremax_chapter_mastery_local_bundle_20261115.py"
spec=importlib.util.spec_from_file_location("mastery_bundle_installer",PATH)
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class MasteryBundleSourceIndentation(unittest.TestCase):
    def test_function_body_blueprint_block_compiles(self):
        original="""def subject_mastery(c,programme):
    governing_blueprint=active_assessment_blueprint(c,programme) if programme else None
    return governing_blueprint
"""
        changed=module.replace_statement_block(
            original,module.OLD_BLUEPRINT,module.NEW_BLUEPRINT,"blueprint")
        self.assertIn("    else:\n        _b=",changed)
        self.assertIn("        governing_blueprint=",changed)
        compile(changed,"<blueprint-fix>","exec")

    def test_nested_loop_policy_block_compiles(self):
        original="""def mastery(c,level,_read_bundle=None):
    for level in ('Foundation',level):
        policy=mastery_policy(c,level)
        if policy:
            return policy
"""
        changed=module.replace_statement_block(
            original,module.OLD_POLICY,module.NEW_POLICY,"policy")
        self.assertIn("        else:\n            _p=",changed)
        self.assertIn("            policy=_p[level]",changed)
        compile(changed,"<policy-fix>","exec")

    def test_function_body_access_block_compiles(self):
        original="""def access_scope(c,student_id,_read_bundle=None):
    access=get_access_profile(c,student_id)
    return access
"""
        changed=module.replace_statement_block(
            original,module.OLD_ACCESS,module.NEW_ACCESS,"access")
        self.assertIn("    else:\n        _a=",changed)
        compile(changed,"<access-fix>","exec")

    def test_fail_closed_if_target_duplicated(self):
        original="""def duplicate(c,student_id):
    access=get_access_profile(c,student_id)
    access=get_access_profile(c,student_id)
    return access
"""
        with self.assertRaisesRegex(RuntimeError,"STATEMENT_DRIFT"):
            module.replace_statement_block(
                original,module.OLD_ACCESS,module.NEW_ACCESS,"duplicate")

if __name__=="__main__":
    unittest.main()
