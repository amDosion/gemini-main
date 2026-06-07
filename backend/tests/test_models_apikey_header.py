"""W02R-017: the provider API key must not be a GET query parameter.

Secrets in the query string land in access logs, browser history, and Referer
headers. /api/models/{provider} must accept the verification key via a request
header (X-Provider-Api-Key), never via ?apiKey=.
"""

from fastapi import FastAPI

from app.routers.models import models as models_mod


def _params():
    app = FastAPI()
    app.include_router(models_mod.router)
    op = app.openapi()
    return op["paths"]["/api/models/{provider}"]["get"].get("parameters", [])


def test_apikey_not_a_query_param():
    by = {(p["name"], p["in"]) for p in _params()}
    assert ("api_key", "query") not in by
    assert ("apiKey", "query") not in by


def test_apikey_accepted_as_header():
    headers = [p for p in _params() if p["in"] == "header"]
    assert any("api" in p["name"].lower().replace("-", "_") for p in headers)
