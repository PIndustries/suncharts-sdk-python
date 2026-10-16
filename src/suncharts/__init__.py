"""SunCharts API SDK for Python.

Low-level, generated operations live in :mod:`suncharts_api` (regenerated from the public OpenAPI spec);
this package adds the ergonomic layer: OAuth2 client-credentials token caching/refresh, API keys, the partner
relay header, retries with backoff and FHIR pagination.
"""

from suncharts.client import (
    PRODUCTION_BASE_URL,
    SANDBOX_BASE_URL,
    ApiKey,
    ClientCredentials,
    Credentials,
    SunCharts,
    SunChartsError,
)

__version__ = "26.10.16.1"

__all__ = [
    "PRODUCTION_BASE_URL",
    "SANDBOX_BASE_URL",
    "ApiKey",
    "ClientCredentials",
    "Credentials",
    "SunCharts",
    "SunChartsError",
    "__version__",
]
