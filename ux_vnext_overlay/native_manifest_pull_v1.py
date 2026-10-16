"""Complete the existing native MANIFEST_PULL signed-GET handshake."""
import ast
import hashlib
from pathlib import Path
import textwrap


HANDLER = '''class _PowerHouseSameOriginRedirectHandler(urlrequest.HTTPRedirectHandler):
    """Validate every redirect before constructing authenticated requests."""
    def __init__(self, trusted_origin, signed_headers=None):
        super().__init__()
        self.trusted_origin = trusted_origin
        self.signed_headers = signed_headers

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        candidate = _https_origin(newurl, label='Power House redirect URL')
        if candidate != self.trusted_origin:
            raise ValueError('Cross-origin Power House package redirect blocked')
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        if redirected is not None and self.signed_headers is not None:
            return urlrequest.Request(newurl, headers=self.signed_headers(newurl), method='GET')
        return redirected
'''

DOWNLOAD = '''def _manifest_pull_signed_headers(url, token, secret):
    from urllib.parse import unquote
    # Flask's native handler signs request.path, which is decoded once and excludes query.
    path = unquote(urlparse(url).path) or '/'
    message_id = 'MSG::SCOREMAX::PULL::' + uuid.uuid4().hex
    sent_at = utcnow()
    content_sha = hashlib.sha256(b'').hexdigest()
    return {'Accept': 'application/zip', 'Authorization': 'Bearer ' + token,
            'X-Message-Id': message_id, 'X-Sent-At': sent_at,
            'X-Content-SHA256': content_sha,
            'X-Signature': 'hmac-sha256=' + signature('GET', path, message_id, sent_at, content_sha, secret)}


def _manifest_pull_retryable(exc):
    # HTTPError is also a URLError: classify its status before the broad network class.
    if isinstance(exc, urlerror.HTTPError):
        return int(exc.code) in {408, 425, 429, 500, 502, 503, 504}
    return isinstance(exc, (TimeoutError, ConnectionError, urlerror.URLError))


def _download_manifest_package(url, timeout=20):
    package_url, trusted_origin = _validate_power_house_package_url(url)
    # The trusted-origin check must precede every credential read.
    token = _manifest_pull_credentials().strip()
    secret = os.environ.get('SCOREMAX_TO_POWER_HOUSE_HMAC_SECRET', '').strip()
    if not token or not secret:
        raise ValueError('Power House signed package credentials are not configured')
    signed_headers = lambda target: _manifest_pull_signed_headers(target, token, secret)
    req = urlrequest.Request(package_url, headers=signed_headers(package_url), method='GET')
    opener = urlrequest.build_opener(_PowerHouseSameOriginRedirectHandler(trusted_origin, signed_headers))
    with opener.open(req, timeout=timeout) as rr:
        return rr.read()
'''


def apply(root):
    p = Path(root) / 'scoremax_integration_v1.py'
    text = p.read_text()
    expected = {'_PowerHouseSameOriginRedirectHandler': '2950d1f2d40032c3223ecd928dfb0fb50a4664a560b60d4fdf92c53dc250dbed',
                '_download_manifest_package': '67121a3884fe13e2d6b6eed5f59e726e4f420d26a60f6e45cf3dd882903f64ec'}
    for name, replacement in (('_PowerHouseSameOriginRedirectHandler', HANDLER), ('_download_manifest_package', DOWNLOAD)):
        node = next(n for n in ast.parse(text).body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name == name)
        old = ast.get_source_segment(text, node)
        assert hashlib.sha256(old.encode()).hexdigest() == expected[name], 'NATIVE_PULL_BOUNDARY_DRIFT:' + name
        text = text.replace(old, textwrap.dedent(replacement).rstrip(), 1)
    old = "retryable=isinstance(exc,(TimeoutError,ConnectionError,urlerror.URLError)) or (isinstance(exc,urlerror.HTTPError) and int(getattr(exc,'code',0) or 0) in {408,425,429,500,502,503,504})"
    assert text.count(old) == 1
    text = text.replace(old, 'retryable=_manifest_pull_retryable(exc)', 1)
    old_code = "code='MANIFEST_PULL_TRANSPORT' if retryable else 'MANIFEST_PULL_INTEGRITY'"
    assert text.count(old_code) == 1
    text = text.replace(old_code, "code='MANIFEST_PULL_HTTP' if isinstance(exc,urlerror.HTTPError) else ('MANIFEST_PULL_TRANSPORT' if retryable else 'MANIFEST_PULL_INTEGRITY')", 1)
    compile(text, str(p), 'exec')
    p.write_text(text)
    print('SCOREMAX_NATIVE_MANIFEST_PULL_INSTALLED signed_get=true origin_fenced=true http_status_classified=true')
