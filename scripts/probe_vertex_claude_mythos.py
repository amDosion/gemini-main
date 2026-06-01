#!/usr/bin/env python3
"""Probe whether the saved Vertex AI config can access Claude Mythos.

The script is intentionally read-only:
- reads VertexAIConfig rows from the local database;
- decrypts the saved service account JSON in memory;
- requests a short-lived OAuth token;
- probes Anthropic publisher model endpoints with a one-token request.

It never prints credentials, access tokens, or full project IDs.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.database import SessionLocal  # noqa: E402
from app.core.encryption import decrypt_data, is_encrypted  # noqa: E402
from app.models.db_models import VertexAIConfig  # noqa: E402


DEFAULT_MYTHOS_CANDIDATES = [
    "claude-mythos",
    "claude-mythos-preview",
    "claude-mythos-preview@20260407",
    "claude-mythos-20260407",
    "claude-mythos@20260407",
    "claude-capybara",
    "claude-capybara-preview",
    "claude-capybara-20260407",
    "claude-capybara@20260407",
]

CONTROL_MODELS = [
    "claude-sonnet-4-6",
    "claude-opus-4-7",
]

DEFAULT_CLAUDE_LOCATIONS = [
    "us-east5",
    "europe-west1",
    "asia-southeast1",
    "global",
]


@dataclass(frozen=True)
class VertexConfig:
    row_id: int
    user_id: str
    project_id: str
    location: str
    credentials_json: str


def mask_value(value: str | None, *, keep_prefix: int = 4, keep_suffix: int = 3) -> str:
    if not value:
        return "<missing>"
    if len(value) <= keep_prefix + keep_suffix + 2:
        return value[:2] + "***"
    return f"{value[:keep_prefix]}***{value[-keep_suffix:]}"


def dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def endpoint_host(location: str) -> str:
    if location == "global":
        return "aiplatform.googleapis.com"
    return f"{location}-aiplatform.googleapis.com"


def model_url(project_id: str, location: str, model_id: str, method: str | None = None) -> str:
    host = endpoint_host(location)
    encoded_project = quote(project_id, safe="")
    encoded_location = quote(location, safe="")
    encoded_model = quote(model_id, safe="")
    base = (
        f"https://{host}/v1/projects/{encoded_project}/locations/{encoded_location}"
        f"/publishers/anthropic/models/{encoded_model}"
    )
    return f"{base}:{method}" if method else base


def list_url(project_id: str, location: str) -> str:
    host = endpoint_host(location)
    return (
        f"https://{host}/v1/projects/{quote(project_id, safe='')}"
        f"/locations/{quote(location, safe='')}/publishers/anthropic/models"
    )


def redact_sensitive(text: str, project_id: str | None = None) -> str:
    if project_id:
        text = text.replace(project_id, mask_value(project_id))
    return text


def summarize_error(response: requests.Response, project_id: str | None = None) -> str:
    content_type = response.headers.get("content-type", "")
    if "json" not in content_type.lower():
        text = response.text.strip().replace("\n", " ")
        return redact_sensitive(text[:240], project_id) or f"HTTP {response.status_code}"

    try:
        payload = response.json()
    except Exception:
        return redact_sensitive(response.text[:240], project_id)

    error = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict):
        status = error.get("status") or "UNKNOWN"
        message = str(error.get("message") or "").strip()
        return redact_sensitive(f"{status}: {message[:240]}", project_id)
    return redact_sensitive(json.dumps(payload, ensure_ascii=False)[:240], project_id)


def load_vertex_configs() -> list[VertexConfig]:
    db = SessionLocal()
    try:
        rows = (
            db.query(VertexAIConfig)
            .filter(
                VertexAIConfig.api_mode == "vertex_ai",
                VertexAIConfig.vertex_ai_project_id.isnot(None),
                VertexAIConfig.vertex_ai_credentials_json.isnot(None),
            )
            .all()
        )

        configs: list[VertexConfig] = []
        for row in rows:
            raw_credentials = row.vertex_ai_credentials_json or ""
            credentials_json = (
                decrypt_data(raw_credentials, silent=True)
                if is_encrypted(raw_credentials)
                else raw_credentials
            )
            configs.append(
                VertexConfig(
                    row_id=int(row.id),
                    user_id=str(row.user_id),
                    project_id=str(row.vertex_ai_project_id or ""),
                    location=str(row.vertex_ai_location or "us-central1"),
                    credentials_json=credentials_json,
                )
            )
        return configs
    finally:
        db.close()


def auth_headers(credentials_json: str) -> dict[str, str]:
    credentials_info = json.loads(credentials_json)
    credentials = service_account.Credentials.from_service_account_info(
        credentials_info,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    credentials.refresh(Request())
    return {
        "Authorization": f"Bearer {credentials.token}",
        "Content-Type": "application/json; charset=utf-8",
    }


def probe_list(project_id: str, location: str, headers: dict[str, str], timeout: int) -> None:
    try:
        response = requests.get(list_url(project_id, location), headers=headers, timeout=timeout)
    except requests.RequestException as exc:
        print(f"  LIST {location}: REQUEST_ERROR {type(exc).__name__}: {str(exc)[:180]}")
        return

    if response.ok:
        payload = response.json()
        models = payload.get("publisherModels") or payload.get("models") or []
        print(f"  LIST {location}: OK count={len(models)}")
        for model in models[:30]:
            if not isinstance(model, dict):
                continue
            name = str(model.get("name") or model.get("publisherModelTemplate") or "")
            display_name = str(model.get("displayName") or model.get("display_name") or "")
            print(f"    - {name.split('/')[-1] or name}" + (f" | {display_name}" if display_name else ""))
        return

    print(f"  LIST {location}: HTTP {response.status_code} {summarize_error(response, project_id)}")


def probe_model(
    project_id: str,
    location: str,
    model_id: str,
    headers: dict[str, str],
    timeout: int,
    *,
    send_predict: bool,
) -> None:
    try:
        get_response = requests.get(
            model_url(project_id, location, model_id),
            headers=headers,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        print(
            f"  GET  {location:15s} {model_id:34s}: "
            f"REQUEST_ERROR {type(exc).__name__}: {str(exc)[:180]}"
        )
        get_response = None

    if get_response is not None:
        get_status = "OK" if get_response.ok else f"HTTP {get_response.status_code}"
        get_detail = "" if get_response.ok else f" {summarize_error(get_response, project_id)}"
        print(f"  GET  {location:15s} {model_id:34s}: {get_status}{get_detail}")

    if not send_predict:
        return

    body = {
        "anthropic_version": "vertex-2023-10-16",
        "messages": [{"role": "user", "content": "Reply with exactly OK."}],
        "max_tokens": 1,
        "stream": False,
    }
    try:
        predict_response = requests.post(
            model_url(project_id, location, model_id, "rawPredict"),
            headers=headers,
            json=body,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        print(
            f"  POST {location:15s} {model_id:34s}: "
            f"REQUEST_ERROR {type(exc).__name__}: {str(exc)[:180]}"
        )
        return

    if predict_response.ok:
        payload = predict_response.json()
        response_model = payload.get("model") or model_id
        content = payload.get("content") or []
        text = ""
        if content and isinstance(content, list) and isinstance(content[0], dict):
            text = str(content[0].get("text") or "").replace("\n", " ")[:80]
        print(f"  POST {location:15s} {model_id:34s}: OK model={response_model} text={text!r}")
        return

    print(
        f"  POST {location:15s} {model_id:34s}: "
        f"HTTP {predict_response.status_code} {summarize_error(predict_response, project_id)}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model",
        action="append",
        dest="models",
        help="Model ID to probe. Repeatable. Defaults to Claude Mythos candidate names.",
    )
    parser.add_argument(
        "--location",
        action="append",
        dest="locations",
        help="Vertex AI location to probe. Repeatable. Defaults to saved location plus known Claude regions.",
    )
    parser.add_argument(
        "--include-controls",
        action="store_true",
        help="Also probe known public Claude model IDs to verify Anthropic access generally.",
    )
    parser.add_argument(
        "--no-predict",
        action="store_true",
        help="Only GET model metadata/list endpoints; do not send rawPredict requests.",
    )
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    configs = load_vertex_configs()
    print(f"vertex_config_rows={len(configs)}")
    if not configs:
        print("No saved Vertex AI config rows were found.")
        return 1

    requested_models = args.models or DEFAULT_MYTHOS_CANDIDATES
    if args.include_controls:
        requested_models = [*CONTROL_MODELS, *requested_models]
    models = dedupe(requested_models)

    for config in configs:
        print(
            f"config[{config.row_id}] "
            f"user={mask_value(config.user_id)} "
            f"project={mask_value(config.project_id)} "
            f"saved_location={config.location}"
        )
        try:
            headers = auth_headers(config.credentials_json)
        except Exception as exc:
            print(f"  auth_error={type(exc).__name__}: {str(exc)[:240]}")
            continue

        locations = dedupe(
            args.locations
            or [config.location, *DEFAULT_CLAUDE_LOCATIONS]
        )

        for location in locations:
            probe_list(config.project_id, location, headers, args.timeout)

        for model_id in models:
            for location in locations:
                probe_model(
                    config.project_id,
                    location,
                    model_id,
                    headers,
                    args.timeout,
                    send_predict=not args.no_predict,
                )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
