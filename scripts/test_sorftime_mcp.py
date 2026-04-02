#!/usr/bin/env python3
"""
Sorftime MCP quick test helper.

Usage examples:
  backend/.venv/bin/python scripts/test_sorftime_mcp.py --key YOUR_KEY --list-only
  backend/.venv/bin/python scripts/test_sorftime_mcp.py --key YOUR_KEY
  backend/.venv/bin/python scripts/test_sorftime_mcp.py --key YOUR_KEY \
    --tool get_product_details --args '{"site":"US","asin":"B0CXX"}'
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qsl, urlunparse

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.services.mcp.mcp_manager import MCPManager
from backend.app.services.mcp.types import MCPServerConfig, MCPServerType


def _attach_key(url: str, key: str | None) -> str:
    if not key:
        return url
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["key"] = key
    return urlunparse(parsed._replace(query=urlencode(query)))


def _parse_json_args(raw: str) -> dict:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid --args JSON: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise ValueError("--args must be a JSON object")
    return payload


async def _run(url: str, tool: str, tool_args: dict, list_only: bool) -> int:
    manager = MCPManager()
    session_id = "sorftime-cli-test"
    config = MCPServerConfig(
        server_type=MCPServerType.STREAMABLE_HTTP,
        url=url,
    )

    try:
        await manager.create_session(session_id, config)
        tools = await manager.list_tools(session_id)
        tool_names = [t.name for t in tools]
        print("tools:", tool_names)

        if list_only:
            return 0

        target = tool if tool in tool_names else (tool_names[0] if tool_names else tool)
        if target != tool:
            print(f"warning: tool '{tool}' not found, fallback to '{target}'")

        result = await manager.call_tool(session_id, target, tool_args if target == tool else {})
        print("call.success:", result.success)
        print("call.is_error:", result.is_error)
        print("call.error:", result.error)
        print("call.result:", result.result)
        return 0 if result.success else 2
    finally:
        await manager.close_all()


def main() -> int:
    parser = argparse.ArgumentParser(description="Sorftime MCP quick test helper")
    parser.add_argument("--url", default="https://mcp.sorftime.com", help="Base MCP URL")
    parser.add_argument("--key", default="", help="Sorftime key; appended as ?key=...")
    parser.add_argument("--tool", default="category_search", help="Tool name to call")
    parser.add_argument(
        "--args",
        default='{"site":"US","searchName":"pet supplies"}',
        help="Tool arguments as JSON object",
    )
    parser.add_argument("--list-only", action="store_true", help="Only list tools")
    args = parser.parse_args()

    final_url = _attach_key(args.url, args.key or None)
    try:
        payload = _parse_json_args(args.args)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1

    return asyncio.run(_run(final_url, args.tool, payload, args.list_only))


if __name__ == "__main__":
    raise SystemExit(main())
