from __future__ import annotations

import base64
import json
import random
import threading
import time
import urllib.parse
from typing import Any, Callable, Dict, Iterator, Optional

import urllib3

import suncharts_api
from suncharts_api import api as _api
from suncharts_api.api_client import ApiClient

PRODUCTION_BASE_URL = "https://api.suncharts.app"
SANDBOX_BASE_URL = "https://sandbox-api.suncharts.app"
USER_AGENT = "suncharts-sdk-python/26.10.16.1"
IDEMPOTENT = {"GET", "HEAD", "PUT", "DELETE", "OPTIONS"}


class SunChartsError(Exception):
    """Non-2xx response. Branch on ``status`` and ``code`` (the API's stable ``error`` field)."""

    def __init__(self, status: int, code: Optional[str], message: str, body: Any = None):
        super().__init__(f"{status} {code or ''}: {message}".strip())
        self.status, self.code, self.message, self.body = status, code, message, body

    @property
    def sub_code(self) -> Optional[str]:
        """409 sub-code, e.g. ``partner_delivery_required``."""
        return self.message.split(":", 1)[0] if self.status == 409 and ":" in self.message else None

    @classmethod
    def from_body(cls, status: int, raw: bytes) -> "SunChartsError":
        try:
            body = json.loads(raw or b"{}")
        except ValueError:
            body = raw.decode("utf-8", "replace")
        if isinstance(body, dict):
            return cls(status, body.get("error"), str(body.get("message") or body.get("error_description") or ""), body)
        return cls(status, None, str(body)[:200], body)


class Credentials:
    """Partner credentials; returns the bearer value for a request."""

    def bearer(self) -> str:  # pragma: no cover - interface
        raise NotImplementedError

    def invalidate(self) -> None:
        """Called after a partner-realm 401; token-based credentials drop their cache."""


class ApiKey(Credentials):
    """Long-lived API key (``sk_test_…`` / ``sk_live_…``)."""

    def __init__(self, key: str):
        self._key = key

    def bearer(self) -> str:
        return self._key

    def __repr__(self) -> str:
        return "ApiKey(***)"


class ClientCredentials(Credentials):
    """OAuth2 client credentials (RFC 6749 §4.4) with a thread-safe token cache refreshed 60 s before expiry."""

    def __init__(self, base_url: str, client_id: str, client_secret: str, scope: str = "",
                 http: Optional[urllib3.PoolManager] = None, clock: Callable[[], float] = time.time,
                 token_path: str = "/oauth/token"):
        self.token_url = base_url.rstrip("/") + token_path
        self.client_id, self._secret, self.scope = client_id, client_secret, scope
        self._http = http or urllib3.PoolManager()
        self._clock = clock
        self._lock = threading.Lock()
        self._token: Optional[str] = None
        self._expires_at = 0.0

    def bearer(self) -> str:
        with self._lock:
            if self._token and self._clock() < self._expires_at - 60:
                return self._token
            fields = {"grant_type": "client_credentials"}
            if self.scope:
                fields["scope"] = self.scope
            basic = base64.b64encode(f"{self.client_id}:{self._secret}".encode()).decode()
            r = self._http.request("POST", self.token_url, body=urllib.parse.urlencode(fields),
                                   headers={"Authorization": f"Basic {basic}", "User-Agent": USER_AGENT,
                                            "Content-Type": "application/x-www-form-urlencoded",
                                            "Accept": "application/json"})
            if r.status >= 400:
                raise SunChartsError.from_body(r.status, r.data)
            data = json.loads(r.data)
            self._token = data["access_token"]
            self._expires_at = self._clock() + int(data.get("expires_in", 3600))
            return self._token

    def invalidate(self) -> None:
        with self._lock:
            self._token, self._expires_at = None, 0.0

    def __repr__(self) -> str:
        return f"ClientCredentials(client_id={self.client_id!r}, client_secret=***)"


class _AuthedApiClient(ApiClient):
    """Generated ApiClient + credentials, relay header, 401 refresh-once and retries."""

    def __init__(self, sdk: "SunCharts"):
        cfg = suncharts_api.Configuration(host=sdk.base_url)
        super().__init__(cfg)
        self.user_agent = sdk.user_agent
        self._sdk = sdk

    def call_api(self, method, url, header_params=None, body=None, post_params=None, _request_timeout=None):
        sdk = self._sdk
        attempt = 0
        refreshed = False
        while True:
            headers = dict(header_params or {})
            headers.update(sdk._auth_headers())
            resp = super().call_api(method, url, headers, body, post_params, _request_timeout or sdk.timeout)
            status = resp.status
            if status == 401 and sdk.credentials is not None and not refreshed and _partner_realm(resp):
                sdk.credentials.invalidate()
                refreshed = True
                continue
            retryable = status == 429 or (status in (502, 503, 504) and method.upper() in IDEMPOTENT)
            if retryable and attempt < sdk.max_retries:
                time.sleep(_backoff(attempt, resp.getheader("Retry-After")))
                attempt += 1
                continue
            return resp


def _partner_realm(resp) -> bool:
    www = resp.getheader("WWW-Authenticate") or ""
    return 'realm="partner"' in www or not www


def _backoff(attempt: int, retry_after: Optional[str]) -> float:
    if retry_after:
        try:
            return min(float(retry_after), 60.0)
        except ValueError:
            pass
    return 0.5 * (2 ** attempt) * (0.5 + random.random() / 2)


class SunCharts:
    """SunCharts API client.

    >>> sc = SunCharts.client_credentials(CLIENT_ID, CLIENT_SECRET)          # sandbox by default
    >>> sc.partner_me()["partner"]["name"]
    >>> user = sc.with_user_token(access_token)   # end-user calls (Authorization) + partner relay header
    >>> user.today()

    Every generated operation is also available, already authenticated, via ``sc.partner``, ``sc.auth``,
    ``sc.patients`` … (``suncharts_api.api.*Api`` instances).
    """

    def __init__(self, base_url: str = SANDBOX_BASE_URL, credentials: Optional[Credentials] = None, *,
                 user_token: Optional[str] = None, end_user_ip: Optional[str] = None, max_retries: int = 3,
                 timeout: float = 30.0, user_agent: str = USER_AGENT):
        self.base_url = base_url.rstrip("/")
        self.credentials = credentials
        self.user_token = user_token
        self.end_user_ip = end_user_ip
        self.max_retries = max_retries
        self.timeout = timeout
        self.user_agent = user_agent
        self.api_client = _AuthedApiClient(self)
        for name in ("Oauth", "Partner", "Auth", "Connections", "Patients", "Appointments", "Encounters",
                     "Notes", "Vitals", "Problems", "Allergies", "Medications", "Documents", "Messages",
                     "Directories", "Meta"):
            setattr(self, name.lower(), getattr(_api, f"{name}Api")(self.api_client))

    # ---- construction --------------------------------------------------------------------------------
    @classmethod
    def client_credentials(cls, client_id: str, client_secret: str, base_url: str = SANDBOX_BASE_URL,
                           scope: str = "", **kw: Any) -> "SunCharts":
        return cls(base_url, ClientCredentials(base_url, client_id, client_secret, scope), **kw)

    @classmethod
    def api_key(cls, key: str, base_url: str = SANDBOX_BASE_URL, **kw: Any) -> "SunCharts":
        return cls(base_url, ApiKey(key), **kw)

    def with_user_token(self, access_token: str, end_user_ip: Optional[str] = None) -> "SunCharts":
        """Same partner credentials, acting for a signed-in user (their token goes in ``Authorization``)."""
        return SunCharts(self.base_url, self.credentials, user_token=access_token,
                         end_user_ip=end_user_ip or self.end_user_ip, max_retries=self.max_retries,
                         timeout=self.timeout, user_agent=self.user_agent)

    def _auth_headers(self) -> Dict[str, str]:
        h: Dict[str, str] = {}
        if self.credentials is not None:
            bearer = f"Bearer {self.credentials.bearer()}"
            if self.user_token:
                h["X-Partner-Authorization"] = bearer
            else:
                h["Authorization"] = bearer
        if self.user_token:
            h["Authorization"] = f"Bearer {self.user_token}"
        if self.end_user_ip:
            h["X-End-User-IP"] = self.end_user_ip
        return h

    # ---- low level ----------------------------------------------------------------------------------
    def request(self, method: str, path: str, *, query: Optional[Dict[str, Any]] = None,
                json_body: Any = None) -> Any:
        """Authenticated JSON request to any path (returns decoded JSON; raises SunChartsError on non-2xx)."""
        url = self.base_url + "/" + path.lstrip("/")
        if query:
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode({k: v for k, v in query.items() if v is not None}, doseq=True)
        headers = {"Accept": "application/json", "User-Agent": self.user_agent}
        if json_body is not None:
            headers["Content-Type"] = "application/json"
        resp = self.api_client.call_api(method.upper(), url, headers, json_body)
        resp.read()
        if resp.status >= 400:
            raise SunChartsError.from_body(resp.status, resp.data)
        return json.loads(resp.data) if resp.data else None

    # ---- convenience (plain dicts; typed models via the generated APIs) -------------------------------
    def health(self) -> Dict[str, Any]:
        return self.request("GET", "/health")

    def partner_me(self) -> Dict[str, Any]:
        return self.request("GET", "/api/v1/partner/me")

    def list_tenants(self) -> list:
        return self.request("GET", "/api/v1/partner/tenants").get("tenants", [])

    def create_tenant(self, tenant: Dict[str, Any]) -> Dict[str, Any]:
        return self.request("POST", "/api/v1/partner/tenants", json_body=tenant)

    def me(self) -> Dict[str, Any]:
        return self.request("GET", "/api/v1/me")

    def today(self, **query: Any) -> Dict[str, Any]:
        return self.request("GET", "/api/v1/today", query=query)

    def connections(self) -> Any:
        return self.request("GET", "/api/v1/connections")

    def fhir_search(self, connection_id: str, resource: str, **params: Any) -> Dict[str, Any]:
        """One page of a FHIR search (a Bundle)."""
        cid = urllib.parse.quote(connection_id, safe="")
        return self.request("GET", f"/api/v1/connections/{cid}/fhir/{resource}", query=params)

    def fhir_search_all(self, connection_id: str, resource: str, max_pages: int = 50, **params: Any) -> Iterator[Dict[str, Any]]:
        """Iterate resources across pages, following the Bundle's ``next`` link."""
        cid = urllib.parse.quote(connection_id, safe="")
        base = f"/api/v1/connections/{cid}/fhir/{resource}"
        query: Optional[Dict[str, Any]] = params
        for _ in range(max_pages):
            bundle = self.request("GET", base, query=query)
            for e in bundle.get("entry") or []:
                if "resource" in e:
                    yield e["resource"]
            nxt = next((l.get("url") for l in bundle.get("link") or [] if l.get("relation") == "next"), None)
            if not nxt:
                return
            query = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(nxt).query))
