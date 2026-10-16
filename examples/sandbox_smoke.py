"""Smoke test against the SunCharts sandbox: OAuth2 token + a few read calls.

    export SUNCHARTS_CLIENT_ID=pc_... SUNCHARTS_CLIENT_SECRET=...   # from https://sandbox-api.suncharts.app/partners/
    python examples/sandbox_smoke.py
"""
import os

from suncharts import SANDBOX_BASE_URL, SunCharts

sc = SunCharts.client_credentials(
    os.environ["SUNCHARTS_CLIENT_ID"],
    os.environ["SUNCHARTS_CLIENT_SECRET"],
    base_url=os.environ.get("SUNCHARTS_BASE_URL", SANDBOX_BASE_URL),
    scope="partner.read tenants.read",
)

me = sc.partner.partner_me()  # generated, typed (suncharts_api.models.PartnerMe)
print("partner:", me.partner.name if me.partner else None)
tenants = sc.list_tenants()  # ergonomic helper (plain dicts)
print("tenants:", [t["slug"] for t in tenants])
