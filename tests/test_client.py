import json
import re

import pytest
from werkzeug import Response

from suncharts import ApiKey, SunCharts, SunChartsError


def token_handler(counter):
    def h(req):
        counter.append(req.headers.get("Authorization"))
        return Response(json.dumps({"access_token": f"pt_{len(counter)}", "token_type": "Bearer", "expires_in": 3600}),
                        content_type="application/json")
    return h


def test_client_credentials_caches_token(httpserver):
    calls = []
    httpserver.expect_request("/oauth/token", method="POST").respond_with_handler(token_handler(calls))
    httpserver.expect_request("/api/v1/partner/me", headers={"Authorization": "Bearer pt_1"}).respond_with_json(
        {"partner": {"id": "p1", "slug": "acme", "name": "Acme"}, "app": {"client_id": "c", "scopes": []}, "branding": {}})
    sc = SunCharts.client_credentials("cid", "sec", base_url=httpserver.url_for(""))
    assert sc.partner_me()["partner"]["name"] == "Acme"
    assert sc.partner.partner_me().partner.name == "Acme"  # generated typed op, same auth
    assert len(calls) == 1 and calls[0].startswith("Basic ")


def test_refreshes_token_once_on_partner_401(httpserver):
    calls = []
    httpserver.expect_request("/oauth/token").respond_with_handler(token_handler(calls))
    httpserver.expect_oneshot_request("/api/v1/partner/tenants").respond_with_json(
        {"error": "unauthorized", "message": "expired"}, status=401, headers={"WWW-Authenticate": 'Bearer realm="partner"'})
    httpserver.expect_oneshot_request("/api/v1/partner/tenants").respond_with_json({"tenants": [{"id": "t"}], "next_cursor": None})
    sc = SunCharts.client_credentials("cid", "sec", base_url=httpserver.url_for(""))
    assert sc.list_tenants() == [{"id": "t"}]
    assert len(calls) == 2


def test_retries_429_and_raises_typed_errors(httpserver):
    httpserver.expect_ordered_request("/api/v1/me").respond_with_json({"error": "rate_limited", "message": "slow"}, status=429, headers={"Retry-After": "0"})
    httpserver.expect_ordered_request("/api/v1/me").respond_with_json({"error": "conflict", "message": "partner_delivery_required: verify domain"}, status=409)
    sc = SunCharts(httpserver.url_for(""), ApiKey("sk_test_x"))
    with pytest.raises(SunChartsError) as e:
        sc.me()
    assert e.value.status == 409 and e.value.code == "conflict" and e.value.sub_code == "partner_delivery_required"


def test_user_token_moves_partner_credentials_to_relay_header(httpserver):
    httpserver.expect_request("/api/v1/today", headers={"Authorization": "Bearer user-at", "X-Partner-Authorization": "Bearer sk_test_x",
                                                        "X-End-User-IP": "203.0.113.7"}).respond_with_json({"appointments": []})
    sc = SunCharts(httpserver.url_for(""), ApiKey("sk_test_x")).with_user_token("user-at", end_user_ip="203.0.113.7")
    assert sc.today(date="2026-10-16") == {"appointments": []}


def test_fhir_search_all_follows_next_links(httpserver):
    base = "/api/v1/connections/c1/fhir/Patient"
    httpserver.expect_ordered_request(base, query_string="name=lee").respond_with_json({"resourceType": "Bundle", "entry": [{"resource": {"id": "1"}}],
        "link": [{"relation": "next", "url": "https://x/fhir/Patient?name=lee&_page=2"}]})
    httpserver.expect_ordered_request(base, query_string="name=lee&_page=2").respond_with_json({"resourceType": "Bundle", "entry": [{"resource": {"id": "2"}}]})
    sc = SunCharts(httpserver.url_for(""), ApiKey("k")).with_user_token("u")
    assert [r["id"] for r in sc.fhir_search_all("c1", "Patient", name="lee")] == ["1", "2"]


def test_convenience_paths_exist_in_spec():
    """The hand-written helpers must only call documented operations (guards against drift)."""
    spec = json.load(open("openapi.json"))
    src = open("src/suncharts/client.py").read()
    used = set(re.findall(r'"(/(?:api/v1|health)[^"{]*)"', src)) | {p.split("{")[0] for p in re.findall(r'f"(/api/v1/[^"]*)"', src)}
    documented = list(spec["paths"])
    for u in used:
        assert any(d == u or d.startswith(u) for d in documented), f"{u} not in openapi.json"
