# ScoreMax V6.5.6 — Power House Manifest Explicit-Port Normalisation Rectification

V6.5.6 is a narrow security child of the exact frozen ScoreMax V6.5.5 candidate whose ZIP SHA-256 is:

`d9cf823392ad405e82e10ca25354d0058e6ae740ef7ea52c811f11bd741a35ab`

## Scope lock

Only the explicit-port normalisation defect in the existing Power House MANIFEST_PULL trusted-origin boundary is rectified.

V6.5.5 correctly required HTTPS, exact host/origin matching, no userinfo, controlled ports and same-origin redirects, but `_https_origin()` used `int(port or 443)`. Python reports `:0`, `:00` and `:000` as integer port `0`; boolean fallback therefore incorrectly normalised those explicit ports to the default HTTPS port 443.

V6.5.6 changes only that semantic: port 443 is inferred **only when the URL has no explicit port**. Any explicit port must be within `1..65535`. Non-numeric and out-of-range ports remain fail-closed through `urlparse().port` validation. Direct invalid package URLs are rejected before bearer-token access and before network/opener creation. Redirect targets are validated before urllib constructs/sends the redirected request.

Legitimate same-origin default `:443` and deployment-controlled non-default ports continue to work.

No mastery, learner UX, reviewer architecture, payment, referral, Emergency Intake, blueprint, question-admission, retry-cycle, strict-JSON or Integration Health behavior is redesigned.

Windows qualification remains a separate infrastructure/CI gate and is not a V6.5.6 product-rectification prerequisite.
