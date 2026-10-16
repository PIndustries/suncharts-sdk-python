# SunCharts SDK for Python

Official Python client for the [SunCharts API](https://api.suncharts.app/docs).

- `suncharts_api` — every operation and model, **generated from the public OpenAPI spec** (`openapi.json`), so it
  never drifts from the API.
- `suncharts` — a thin hand-written layer: OAuth2 client-credentials token caching and refresh, API keys, the
  partner relay header, retries with backoff, and FHIR pagination.

Python 3.9+. MIT licensed.

## Install

```bash
pip install "git+https://github.com/PIndustries/suncharts-sdk-python@26.10.16.1"
```

(PyPI package `suncharts-sdk` coming soon.)

## Quickstart (sandbox)

Create a free sandbox account and an app at <https://sandbox-api.suncharts.app/partners/> and copy the
`client_id` / `client_secret`.

```python
import os
from suncharts import SunCharts, SANDBOX_BASE_URL

sc = SunCharts.client_credentials(
    os.environ["SUNCHARTS_CLIENT_ID"], os.environ["SUNCHARTS_CLIENT_SECRET"],
    base_url=SANDBOX_BASE_URL,               # PRODUCTION_BASE_URL = https://api.suncharts.app
    scope="partner.read tenants.read",       # optional subset of your app's scopes
)

me = sc.partner.partner_me()                 # generated, typed model (token fetched & cached for you)
print(me.partner.name)
for t in sc.list_tenants():                  # convenience helper, plain dicts
    print(t["slug"])
```

API key instead of OAuth2: `SunCharts.api_key("sk_test_…")`.

### Acting for an end user (white-label relay)

```python
user = sc.with_user_token(user_access_token, end_user_ip="203.0.113.7")
user.today(date="2026-10-16", tz="America/Chicago")
for patient in user.fhir_search_all(connection_id, "Patient", name="lee"):   # follows Bundle `next` links
    print(patient["id"])
```

Your partner credentials move to `X-Partner-Authorization` and the user's token goes in `Authorization`.

### All operations

Each tag of the API is an authenticated generated client on the `SunCharts` object: `sc.oauth`, `sc.partner`,
`sc.auth`, `sc.connections`, `sc.patients`, `sc.appointments`, `sc.encounters`, `sc.notes`, `sc.vitals`,
`sc.problems`, `sc.allergies`, `sc.medications`, `sc.documents`, `sc.messages`, `sc.directories`, `sc.meta`.
For anything else, `sc.request("GET", "/api/v1/...")`.

### Errors and retries

Non-2xx responses raise `SunChartsError` with `.status`, `.code` (the API's stable `error`) and `.sub_code`
(e.g. `partner_delivery_required` on 409). Generated operations raise `suncharts_api.ApiException`.
`429` is retried after `Retry-After`; `502/503/504` are retried with jittered backoff on idempotent requests
(`max_retries=3`); a partner-realm `401` refreshes the OAuth token once.

## Examples

`examples/sandbox_smoke.py` — OAuth2 token + reads against the sandbox:

```bash
SUNCHARTS_CLIENT_ID=… SUNCHARTS_CLIENT_SECRET=… python examples/sandbox_smoke.py
```

## Development

```bash
pip install -e '.[test]' && pytest
scripts/generate.sh            # regenerate src/suncharts_api from openapi.json (needs Java 11+)
```

`openapi.json` is synced from the API automatically (a pull request is opened when the spec changes); CI fails
if `src/suncharts_api` is not exactly what the generator produces. Don't edit `src/suncharts_api` by hand.

## Versioning

Releases use the P.Industries format `YY.MM.DD.<build-of-day>` (UTC date), e.g. `26.10.16.1`; the git tag is exactly
that (no `v`). PEP 440 accepts the 4-part form, so the package version is identical. Bump with `scripts/version.sh set $(scripts/version.sh next)`; merging a `VERSION` change to
`main` tags the release automatically (`.github/workflows/release.yml`).
