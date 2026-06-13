"""Export the runtime OpenAPI contract for API security tooling."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def export_openapi(output_path: str | Path, *, server_url: str | None = None) -> dict[str, Any]:
    server_url = _normalize_export_server_url(server_url)
    old_server_url = os.environ.get("OPENAPI_SERVER_URL")
    if server_url:
        os.environ["OPENAPI_SERVER_URL"] = server_url

    try:
        from app.main import app

        app.openapi_schema = None
        schema = app.openapi()
    finally:
        if server_url:
            if old_server_url is None:
                os.environ.pop("OPENAPI_SERVER_URL", None)
            else:
                os.environ["OPENAPI_SERVER_URL"] = old_server_url

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return schema


def _normalize_export_server_url(server_url: str | None) -> str | None:
    raw = str(server_url or "").strip()
    if not raw:
        return None
    if raw == "/":
        return "/"

    parsed = urlparse(raw)
    if parsed.scheme == "https" and parsed.netloc:
        return raw.rstrip("/")

    raise ValueError("--server-url must be an HTTPS URL or '/'")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export FastAPI runtime OpenAPI JSON for 42Crunch/API review."
    )
    parser.add_argument(
        "--output",
        default="openapi.json",
        help="Output JSON path, relative to the current working directory.",
    )
    parser.add_argument(
        "--server-url",
        default="",
        help="Optional HTTPS server URL for the exported OpenAPI servers[0].url.",
    )
    args = parser.parse_args()

    schema = export_openapi(args.output, server_url=args.server_url or None)
    operations = sum(
        1
        for path_item in schema.get("paths", {}).values()
        if isinstance(path_item, dict)
        for method, operation in path_item.items()
        if method in {"get", "put", "post", "delete", "patch", "head", "options", "trace"}
        and isinstance(operation, dict)
    )
    print(f"Exported {operations} OpenAPI operations to {args.output}")


if __name__ == "__main__":
    main()
