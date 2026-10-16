# coding: utf-8

# flake8: noqa

"""
    SunCharts API

    Build your own backend on SunCharts. Everything you need is here: this reference, a free sandbox and public SDKs. The API is plain HTTPS + JSON, so any language works; the SDKs are optional conveniences. Machine-readable spec: [`/openapi.json`](/openapi.json) (also `/api/v1/openapi.yaml`).  # Quickstart  1. **Get sandbox credentials** — open the partner console at    [`https://sandbox-api.suncharts.app/partners/`](https://sandbox-api.suncharts.app/partners/), create a sandbox    account (email link, no password), then **Create app**. Copy the `client_id` and `client_secret` (shown once). 2. **Get an access token** (OAuth2 client credentials):  ```bash curl -s https://sandbox-api.suncharts.app/oauth/token \\   -u \"$CLIENT_ID:$CLIENT_SECRET\" \\   -d grant_type=client_credentials -d scope=\"partner.read tenants.read\" # {\"access_token\":\"pt_…\",\"token_type\":\"Bearer\",\"expires_in\":3600,\"scope\":\"partner.read tenants.read\"} ```  3. **Call the API**:  ```bash curl -s https://sandbox-api.suncharts.app/api/v1/partner/me -H \"Authorization: Bearer $ACCESS_TOKEN\" ```  4. **Or use an SDK** (see *SDKs*; Rust shown — PHP, Python and TypeScript work the same way):  ```toml [dependencies] suncharts-sdk = { git = \"https://github.com/PIndustries/suncharts-sdk-rust\", tag = \"v0.4.0\" } ```  ```rust let client = suncharts_sdk::Client::builder(suncharts_sdk::SANDBOX_BASE_URL)     .client_credentials(std::env::var(\"CLIENT_ID\")?, std::env::var(\"CLIENT_SECRET\")?)     .build()?; let me = client.partner_me().await?; // token fetched, cached and refreshed for you ```  # Environments  | Environment | Base URL | Data | |---|---|---| | Sandbox | `https://sandbox-api.suncharts.app` | Simulated EHR data; reset nightly 03:15 America/Chicago (partner accounts, apps and keys are kept) | | Production | `https://api.suncharts.app` | Real clinics |  Sandbox and production are separate systems: credentials from one never work on the other. Sandbox keys start with `sk_test_`, production keys with `sk_live_`. Sandbox apps cannot hold `clinical.write`.  **Sandbox test data.** Every sandbox partner gets a tenant `<your-partner-slug>-test` (\"Sandbox Test Clinic\") with passwordless users `test.owner@example.test` (owner) and `test.clinician@example.test` (clinician); it shows up in `GET /api/v1/partner/tenants` and is re-created after the nightly reset. Sandbox apps start with `email_delivery: partner`, so relayed `auth/magic/*`, signup and invite calls return the `delivery` secret instead of sending mail, and passkey ceremonies use your app's `rp_id`/`auth_origin` exactly as in production. `sandbox-api.p.industries` and `htpi.p.industries` are legacy aliases; use the hosts above.  # Authentication  Two ways to authenticate your **server** (never ship either to a browser or mobile app):  ## OAuth2 client credentials (recommended)  `POST /oauth/token` per [RFC 6749 §4.4](https://www.rfc-editor.org/rfc/rfc6749#section-4.4). Send client authentication as HTTP Basic (`client_id:client_secret`) **or** as `client_id` / `client_secret` body fields; the body may be `application/x-www-form-urlencoded` or JSON. Optional `scope` narrows the token to a subset of your app's scopes. Tokens (`pt_…`) last **1 hour**; request a new one when `expires_in` runs out (the SDK does this). Errors follow RFC 6749 §5.2: `invalid_request`, `invalid_client` (401), `unsupported_grant_type`, `invalid_scope`. `POST /api/v1/partner/token` remains as a legacy JSON alias.  ## API keys  Long-lived keys created in the partner console, optionally with an expiry and a subset of the app's scopes. Send as `Authorization: Bearer sk_…` or `X-API-Key: sk_…`.  **Where to send partner credentials.** Every partner endpoint also accepts them as `X-Partner-Authorization: Bearer <token or key>`; it is checked first, so one request can carry your credentials there and an end user's token in `Authorization`. A `401` caused by partner credentials carries `WWW-Authenticate: Bearer realm=\"partner\"` — fetch a new access token and retry once. Prefer OAuth2 for production; use keys where a token exchange is impractical.  ## Scopes  | Scope | Grants | |---|---| | `partner.read` | Your partner profile, branding and app identity; read auth settings | | `tenants.read` / `tenants.write` | List / create your clinics (tenants) | | `users.passthrough` | Relay end-user sign-in for your users (see *White-label auth relay*) | | `clinical.read` / `clinical.write` | Clinical endpoints (with the end user's token) | | `apps.manage` | Change your app's auth settings via the API |  ## Rotation and revocation  Everything is self-serve in the partner console (`/partners/` on each environment): - **Rotate client secret** — a new secret is issued; the previous one keeps working for a grace window   (default 24 h, up to 7 days) so you can roll deploys without downtime. - **Rotate API key** — issues a replacement with the same scopes; the old key expires after the grace window. - **Revoke** an app or key — takes effect immediately; outstanding access tokens stop working. - Every issue, rotation, revocation and denied token request is in the console's audit log.  ## End-user tokens  Clinical calls run as a clinic user. Your backend signs the user in through the auth endpoints (below) and uses the returned user access token (`userBearer`). Refresh with `POST /api/v1/auth/refresh`.  # White-label auth relay  Your backend can call the end-user auth endpoints (`/api/v1/auth/*`, `/api/v1/signup*`, `/api/v1/invites/*`, `/api/v1/tenant/invites*`) on behalf of your users so they only ever see your brand. Identify your app on those calls with:  ``` X-Partner-Authorization: Bearer <OAuth access token or API key>   (scope users.passthrough) X-End-User-IP: 203.0.113.7                                         (optional; per-user rate limits) ```  Without the header, the endpoints behave as for first-party apps. On relayed calls `device_nonce` is optional (secrets are bound to your app) and no CAPTCHA is required. With it, your app's **auth settings** apply:  | Setting | Effect | |---|---| | `auth_origin` | Your web origin (e.g. `https://app.example.com`): passkey origin and base for links | | `rp_id` | Passkey relying-party ID (your domain; must be the origin host or a parent of it) | | `android_cert_sha256[]` | Your Android signing-cert fingerprints; accepted as passkey origins (`android:apk-key-hash:…`) | | `apple_app_ids[]` | `TEAMID.bundle.id` of your iOS apps (for your associated-domains file) | | `email_link_base` | Link target for sign-in emails; `{token}` placeholder, else `#t=<token>` is appended | | `email_delivery` | `partner` or `platform` (below) |  Set them in the console or with `PATCH /api/v1/partner/auth-settings`. Passkey registration and sign-in then use your RP ID, origins and brand name.  **Email delivery.** With `partner` delivery we send nothing: `auth/magic/start`, `signup/start`, `signup` and `signup/resend` return a `delivery` object (`email`, `token`, `code`, `purpose`, `expires_in_mins`) on your partner-authenticated call only, and you deliver it however you like (`delivery` is `null` when there is nothing to send, e.g. an unknown email on sign-in). With `platform` delivery we send the email under your brand and from-address with links on your origin — available once your custom domain is verified; until then those calls return `409 partner_delivery_required`. Clinic invites for your tenants link to your `auth_origin`.  # Implementing a client (any language)  The contract is the HTTP described here; nothing depends on an SDK. A conforming client:  - **Transport** — HTTPS only, TLS 1.2+. Request and response bodies are UTF-8 JSON   (`Content-Type: application/json`) except `POST /oauth/token`, which also takes   `application/x-www-form-urlencoded`. Send a descriptive `User-Agent` (e.g. `acme-backend/1.4 php/8.3`). - **Data types** — timestamps are RFC 3339 in UTC (`2026-10-16T16:00:00Z`); dates are `YYYY-MM-DD`;   IDs are opaque strings (don't parse them, don't assume UUIDs or length). Absent and `null` mean the same.   **Ignore unknown fields and enum values** you don't recognise: v1 grows additively. - **Token handling** — cache the `access_token` per (client_id, scope) and reuse it until about 60 s before   `expires_in` elapses; then request a new one (there are no refresh tokens for client credentials). On a   `401` from an API call, fetch a fresh token **once** and retry; if it fails again, surface the error.   Never log `client_secret`, access tokens or API keys. - **Errors** — branch on HTTP status and the `error` code (see *Errors*), never on `message`. On `409`,   sub-codes are the text before the first `:` in `message` (e.g. `partner_delivery_required`). - **Retries** — retry `429` after `Retry-After` seconds, and `502/503/504` and network errors on idempotent   requests (`GET`, `PUT`, `DELETE`) with exponential backoff and jitter (e.g. 0.5 s, 1 s, 2 s; max 3 tries).   Don't blindly retry `POST` auth calls (they may send an email). - **Relay** — on end-user auth calls made for your users, add `X-Partner-Authorization: Bearer <token or key>`   and `X-End-User-IP`. Pass the end user's own `Authorization` header (if any) through unchanged. - **Timeouts** — 10 s connect, 30 s total is a good default; FHIR calls proxy to the clinic's EHR and can be   slower.  ### Minimal flow with plain HTTP  ```bash TOKEN=$(curl -s https://sandbox-api.suncharts.app/oauth/token -u \"$CLIENT_ID:$CLIENT_SECRET\" \\   -d grant_type=client_credentials | jq -r .access_token) curl -s https://sandbox-api.suncharts.app/api/v1/partner/tenants -H \"Authorization: Bearer $TOKEN\" # relayed sign-in for one of your users, with partner delivery: curl -s https://sandbox-api.suncharts.app/api/v1/auth/magic/start \\   -H \"X-Partner-Authorization: Bearer $TOKEN\" -H \"X-End-User-IP: 203.0.113.7\" \\   -H 'Content-Type: application/json' -d '{\"email\":\"dr.lee@example.com\"}' # {\"status\":\"sent\",\"message\":\"…\",\"resend_after\":60,\"expires_in\":600,\"code_length\":6, #  \"delivery\":{\"email\":\"dr.lee@example.com\",\"token\":\"…\",\"code\":\"123456\",\"purpose\":\"signin\",\"expires_in_mins\":10}} ```  # Errors  Errors are JSON with a stable, brand-neutral code:  ```json {\"error\": \"bad_request\", \"message\": \"human-readable detail\"} ```  | HTTP | `error` | Meaning | |---|---|---| | 400 | `bad_request` | Invalid input | | 401 | `unauthorized` | Missing, expired or revoked credentials (`invalid_client` on `/oauth/token`) | | 403 | `forbidden` | Credential lacks the scope / access | | 404 | `not_found` | No such resource (or not yours) | | 409 | `conflict` | State conflict (`message` starts with a sub-code such as `partner_delivery_required`) | | 428 | `openemr_link_required` / `openemr_relink_required` | The user must (re)link their EHR account | | 429 | `rate_limited` | Slow down; honour `Retry-After` | | 424 | `upstream_error` | The clinic's EHR failed or timed out; retry idempotent calls with backoff | | 5xx | `internal` | Our side; retry with backoff |  Codes are only ever added within v1.  # Rate limits  - Per app: `rate_limit_per_min` (default **600/min**) shared by its tokens and keys. - Token endpoint: 30 requests/min per source IP. - Auth endpoints: per end user (send `X-End-User-IP` when relaying) and per email. - Exceeding a limit returns `429` with `Retry-After` (seconds). Back off and retry.  # Versioning  - The major version is in the path (`/api/v1`). Within v1 changes are **additive only**: new endpoints,   new optional request fields, new response fields, new error codes. Ignore unknown fields. - Breaking changes ship as `/api/v2` with at least **6 months** of overlap. Deprecated operations are marked   `deprecated` here and answer with `Deprecation` and `Sunset` headers before removal. - The SDKs follow SemVer independently of the API version; minor versions add features, patch versions fix bugs.  # SDKs  Official SDKs are generated from this spec ([`/openapi.json`](/openapi.json)) on every API change, plus a thin hand-written layer for OAuth2 token caching/refresh, API keys, the relay header, retries and pagination.  | Language | Repository | Install | License | |---|---|---|---| | PHP 8.2+ | [`PIndustries/suncharts-sdk-php`](https://github.com/PIndustries/suncharts-sdk-php) | `composer require pindustries/suncharts-sdk-php` (VCS repo until published) | MIT | | Rust | [`PIndustries/suncharts-sdk-rust`](https://github.com/PIndustries/suncharts-sdk-rust) | `suncharts-sdk = { git = \"https://github.com/PIndustries/suncharts-sdk-rust\", tag = \"v0.4.0\" }` | MIT OR Apache-2.0 | | Python 3.9+ | [`PIndustries/suncharts-sdk-python`](https://github.com/PIndustries/suncharts-sdk-python) | `pip install \"git+https://github.com/PIndustries/suncharts-sdk-python@v0.1.0\"` | MIT | | TypeScript / Node 18+ | [`PIndustries/suncharts-sdk-typescript`](https://github.com/PIndustries/suncharts-sdk-typescript) | `npm install github:PIndustries/suncharts-sdk-typescript#v0.1.0` | MIT |  Any other language — generate a client from [`/openapi.json`](/openapi.json).

    The version of the OpenAPI document: 1.1.0
    Generated by OpenAPI Generator (https://openapi-generator.tech)

    Do not edit the class manually.
"""  # noqa: E501


__version__ = "0.0.0"

# Define package exports
__all__ = [
    "AllergiesApi",
    "AppointmentsApi",
    "AuthApi",
    "ConnectionsApi",
    "DirectoriesApi",
    "DocumentsApi",
    "EncountersApi",
    "MedicationsApi",
    "MessagesApi",
    "MetaApi",
    "NotesApi",
    "OauthApi",
    "PartnerApi",
    "PatientsApi",
    "ProblemsApi",
    "VitalsApi",
    "ApiResponse",
    "ApiClient",
    "Configuration",
    "OpenApiException",
    "ApiTypeError",
    "ApiValueError",
    "ApiKeyError",
    "ApiAttributeError",
    "ApiException",
    "Appointment",
    "AppointmentPatient",
    "AuthSettings",
    "ClientCredentialsRequest",
    "ClinicMembership",
    "ClinicSelection",
    "Delivery",
    "Error",
    "FhirBundle",
    "FhirBundleEntryInner",
    "FhirBundleLinkInner",
    "HealthStatus",
    "Invite",
    "InviteDelivery",
    "Login200Response",
    "LoginRequest",
    "MagicSent",
    "MagicStartRequest",
    "MagicVerifyRequest",
    "NewInvite",
    "NewTenant",
    "OAuthError",
    "OAuthTokenRequest",
    "PartnerDeactivateUser200Response",
    "PartnerMe",
    "PartnerMeApp",
    "PartnerMeBranding",
    "PartnerMePartner",
    "PartnerToken",
    "RefreshRequest",
    "SelectClinicRequest",
    "Tenant",
    "TenantPage",
    "TenantUser",
    "TenantUsers",
    "Today",
    "UserTokens",
]

# import apis into sdk package
from suncharts_api.api.allergies_api import AllergiesApi as AllergiesApi
from suncharts_api.api.appointments_api import AppointmentsApi as AppointmentsApi
from suncharts_api.api.auth_api import AuthApi as AuthApi
from suncharts_api.api.connections_api import ConnectionsApi as ConnectionsApi
from suncharts_api.api.directories_api import DirectoriesApi as DirectoriesApi
from suncharts_api.api.documents_api import DocumentsApi as DocumentsApi
from suncharts_api.api.encounters_api import EncountersApi as EncountersApi
from suncharts_api.api.medications_api import MedicationsApi as MedicationsApi
from suncharts_api.api.messages_api import MessagesApi as MessagesApi
from suncharts_api.api.meta_api import MetaApi as MetaApi
from suncharts_api.api.notes_api import NotesApi as NotesApi
from suncharts_api.api.oauth_api import OauthApi as OauthApi
from suncharts_api.api.partner_api import PartnerApi as PartnerApi
from suncharts_api.api.patients_api import PatientsApi as PatientsApi
from suncharts_api.api.problems_api import ProblemsApi as ProblemsApi
from suncharts_api.api.vitals_api import VitalsApi as VitalsApi

# import ApiClient
from suncharts_api.api_response import ApiResponse as ApiResponse
from suncharts_api.api_client import ApiClient as ApiClient
from suncharts_api.configuration import Configuration as Configuration
from suncharts_api.exceptions import OpenApiException as OpenApiException
from suncharts_api.exceptions import ApiTypeError as ApiTypeError
from suncharts_api.exceptions import ApiValueError as ApiValueError
from suncharts_api.exceptions import ApiKeyError as ApiKeyError
from suncharts_api.exceptions import ApiAttributeError as ApiAttributeError
from suncharts_api.exceptions import ApiException as ApiException

# import models into sdk package
from suncharts_api.models.appointment import Appointment as Appointment
from suncharts_api.models.appointment_patient import AppointmentPatient as AppointmentPatient
from suncharts_api.models.auth_settings import AuthSettings as AuthSettings
from suncharts_api.models.client_credentials_request import ClientCredentialsRequest as ClientCredentialsRequest
from suncharts_api.models.clinic_membership import ClinicMembership as ClinicMembership
from suncharts_api.models.clinic_selection import ClinicSelection as ClinicSelection
from suncharts_api.models.delivery import Delivery as Delivery
from suncharts_api.models.error import Error as Error
from suncharts_api.models.fhir_bundle import FhirBundle as FhirBundle
from suncharts_api.models.fhir_bundle_entry_inner import FhirBundleEntryInner as FhirBundleEntryInner
from suncharts_api.models.fhir_bundle_link_inner import FhirBundleLinkInner as FhirBundleLinkInner
from suncharts_api.models.health_status import HealthStatus as HealthStatus
from suncharts_api.models.invite import Invite as Invite
from suncharts_api.models.invite_delivery import InviteDelivery as InviteDelivery
from suncharts_api.models.login200_response import Login200Response as Login200Response
from suncharts_api.models.login_request import LoginRequest as LoginRequest
from suncharts_api.models.magic_sent import MagicSent as MagicSent
from suncharts_api.models.magic_start_request import MagicStartRequest as MagicStartRequest
from suncharts_api.models.magic_verify_request import MagicVerifyRequest as MagicVerifyRequest
from suncharts_api.models.new_invite import NewInvite as NewInvite
from suncharts_api.models.new_tenant import NewTenant as NewTenant
from suncharts_api.models.o_auth_error import OAuthError as OAuthError
from suncharts_api.models.o_auth_token_request import OAuthTokenRequest as OAuthTokenRequest
from suncharts_api.models.partner_deactivate_user200_response import PartnerDeactivateUser200Response as PartnerDeactivateUser200Response
from suncharts_api.models.partner_me import PartnerMe as PartnerMe
from suncharts_api.models.partner_me_app import PartnerMeApp as PartnerMeApp
from suncharts_api.models.partner_me_branding import PartnerMeBranding as PartnerMeBranding
from suncharts_api.models.partner_me_partner import PartnerMePartner as PartnerMePartner
from suncharts_api.models.partner_token import PartnerToken as PartnerToken
from suncharts_api.models.refresh_request import RefreshRequest as RefreshRequest
from suncharts_api.models.select_clinic_request import SelectClinicRequest as SelectClinicRequest
from suncharts_api.models.tenant import Tenant as Tenant
from suncharts_api.models.tenant_page import TenantPage as TenantPage
from suncharts_api.models.tenant_user import TenantUser as TenantUser
from suncharts_api.models.tenant_users import TenantUsers as TenantUsers
from suncharts_api.models.today import Today as Today
from suncharts_api.models.user_tokens import UserTokens as UserTokens

