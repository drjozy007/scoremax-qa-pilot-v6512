"""Check native signed GETs, credential isolation, redirects and HTTP retry rules."""
import argparse
from contextlib import contextmanager
import hashlib
import hmac
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from urllib import error, request

p=argparse.ArgumentParser();p.add_argument('--runtime',default='scoremax_runtime_v669b');args,rest=p.parse_known_args()
sys.path.insert(0,str(Path(args.runtime).resolve()))
import scoremax_integration_v1 as integration

TOKEN='synthetic-native-pull-token'
SECRET='synthetic-native-pull-hmac'
BASE='https://native.example.invalid'
URL=BASE+'/api/integration/v1/content-releases/REL%3A%3ATEST/2026.10.14.1'
PATH='/api/integration/v1/content-releases/REL::TEST/2026.10.14.1'


class PullTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{'SCOREMAX_POWER_HOUSE_BASE_URL':BASE,'SCOREMAX_TO_POWER_HOUSE_TOKEN':TOKEN,'SCOREMAX_TO_POWER_HOUSE_HMAC_SECRET':SECRET})
        self.env.start();self.addCleanup(self.env.stop)

    def validate(self, req, path):
        headers={k.lower():v for k,v in req.header_items()}
        self.assertEqual(headers['authorization'],'Bearer '+TOKEN)
        self.assertEqual(headers['x-content-sha256'],hashlib.sha256(b'').hexdigest())
        canonical='\n'.join(['GET',path,headers['x-message-id'],headers['x-sent-at'],headers['x-content-sha256']])
        expected='hmac-sha256='+hmac.new(SECRET.encode(),canonical.encode(),hashlib.sha256).hexdigest()
        self.assertEqual(headers['x-signature'],expected)
        return headers

    def test_download_signs_native_decoded_path_and_empty_body(self):
        requests=[]
        class Response:
            def __enter__(self):return self
            def __exit__(self,*_):pass
            def read(self, *args):return b'qualified-archive'
        class Opener:
            def open(self,req,timeout):requests.append(req);return Response()
        with patch.object(integration.urlrequest,'build_opener',return_value=Opener()):
            self.assertEqual(integration._download_manifest_package(URL),b'qualified-archive')
            integration._download_manifest_package(URL)
        a=self.validate(requests[0],PATH);b=self.validate(requests[1],PATH)
        self.assertNotEqual(a['x-message-id'],b['x-message-id'])

    def test_wrong_origin_is_rejected_before_credentials_or_network(self):
        with patch.object(integration,'_manifest_pull_credentials') as credentials,patch.object(integration.urlrequest,'build_opener') as network:
            with self.assertRaises(ValueError):integration._download_manifest_package('https://attacker.invalid/package')
            credentials.assert_not_called();network.assert_not_called()

    def test_missing_signing_secret_fails_without_network_or_credential_disclosure(self):
        os.environ.pop('SCOREMAX_TO_POWER_HOUSE_HMAC_SECRET')
        with patch.object(integration.urlrequest,'build_opener') as network:
            with self.assertRaises(ValueError) as caught:integration._download_manifest_package(URL)
            network.assert_not_called();self.assertNotIn(TOKEN,str(caught.exception))

    def test_same_origin_redirect_gets_new_identity_and_signature_for_new_path(self):
        sign=lambda target:integration._manifest_pull_signed_headers(target,TOKEN,SECRET)
        original=request.Request(URL,headers=sign(URL),method='GET')
        handler=integration._PowerHouseSameOriginRedirectHandler(integration._trusted_power_house_origin(),sign)
        redirected=handler.redirect_request(original,None,302,'Found',{},BASE+'/alternate%3Apath')
        a=self.validate(original,PATH);b=self.validate(redirected,'/alternate:path')
        self.assertNotEqual(a['x-message-id'],b['x-message-id'])

    def test_cross_origin_redirect_never_constructs_authenticated_request(self):
        auth=[]
        handler=integration._PowerHouseSameOriginRedirectHandler(integration._trusted_power_house_origin(),lambda target:auth.append(target))
        with self.assertRaises(ValueError):handler.redirect_request(request.Request(URL),None,302,'Found',{},'https://attacker.invalid/collect')
        self.assertEqual(auth,[])

    def test_http_status_is_classified_before_urlerror_parent_class(self):
        for status in (400,401,403,404,409,422):
            with self.subTest(status=status):self.assertFalse(integration._manifest_pull_retryable(error.HTTPError(URL,status,'test',{},None)))
        for status in (408,425,429,500,502,503,504):
            with self.subTest(status=status):self.assertTrue(integration._manifest_pull_retryable(error.HTTPError(URL,status,'test',{},None)))
        self.assertTrue(integration._manifest_pull_retryable(error.URLError('unavailable')))
        self.assertTrue(integration._manifest_pull_retryable(TimeoutError()))
        self.assertFalse(integration._manifest_pull_retryable(ValueError('checksum mismatch')))


if __name__=='__main__':unittest.main(argv=[sys.argv[0]]+rest,verbosity=2)
