import hashlib,importlib.util,json
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location('pure_decode_tested_v4',
    Path(__file__).resolve().parents[2]/'scoremax_runtime_v669b/frozen_context_decode_v4.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
integration=ModuleType('scoremax_integration_v1')
integration.canonical_json=lambda value:json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False)


def seal(value):
    value=dict(value);value['checksum_sha256']=hashlib.sha256(integration.canonical_json(value).encode()).hexdigest()
    return json.dumps(value,ensure_ascii=False)


class Decode(unittest.TestCase):
    def setUp(self):
        m._immutable.cache_clear();self.modules=patch.dict(sys.modules,{'scoremax_integration_v1':integration})
        self.modules.start();self.addCleanup(self.modules.stop);self.addCleanup(m._immutable.cache_clear)

    def test_exact_raw_bytes_validate_once_and_outputs_are_owned(self):
        raw=seal({'schema':'SM-EVIDENCE-CONTEXT-1','question_db_id':17,'programme':'MDCAT','chapter':'opaque/0001 '})
        with patch.object(m,'decode',wraps=m.decode) as decode:
            first=m.context(raw);first['question_db_id']=99
            self.assertEqual(m.context(raw)['question_db_id'],17)
            self.assertEqual(decode.call_count,1)
            self.assertEqual(m.context(raw)['chapter'],'opaque/0001 ')

    def test_checksum_corruption_and_identity_changes_never_borrow_cached_value(self):
        first=seal({'question_db_id':17,'programme':'FSc Part 1'})
        m.context(first)
        self.assertIsNone(m.context(first.replace('17','18')))
        other=seal({'question_db_id':18,'programme':'MDCAT'})
        self.assertEqual(m.context(other),{'question_db_id':18,'programme':'MDCAT'})
        self.assertEqual(m.decode(other),m.context(other))

    def test_nested_and_unknown_metadata_bypass_reuse_preserving_original_semantics(self):
        for value in ({'topic':['nested',{'state':True}]},{'custom_future_field':'opaque/value'}):
            raw=seal(value)
            with patch.object(m,'decode',wraps=m.decode) as decode:
                self.assertEqual(m.context(raw),value);self.assertEqual(m.context(raw),value)
                self.assertGreaterEqual(decode.call_count,2)
        raw=seal({'topic':['nested']});first=m.context(raw);first['topic'].append('changed')
        self.assertEqual(m.context(raw),{'topic':['nested']})

    def test_large_inputs_and_non_string_json_keep_original_decode_without_cache(self):
        for raw in (seal({'topic':'x'*9000}),seal({'topic':'bytes'}).encode()):
            before=m._immutable.cache_info()
            self.assertEqual(m.context(raw),m.decode(raw));self.assertEqual(m._immutable.cache_info(),before)
        for raw in ('{broken','[]','null','{"checksum_sha256":"wrong"}'):
            self.assertIsNone(m.context(raw))

    def test_cache_size_is_bounded_and_does_not_decide_current_programme_or_eligibility(self):
        for i in range(4200):self.assertEqual(m.context(seal({'question_db_id':i})),{'question_db_id':i})
        self.assertEqual(m._immutable.cache_info().currsize,4096)
        self.assertEqual(m.context(seal({'schema':'unrecognized','programme':'unknown'})),
            {'schema':'unrecognized','programme':'unknown'})


if __name__=='__main__':unittest.main(verbosity=2)
