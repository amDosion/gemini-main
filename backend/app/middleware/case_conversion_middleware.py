"""
FastAPI 中间件：自动转换请求和响应的数据格式

功能：
1. 请求：将前端发送的 camelCase 数据转换为 snake_case
   - JSON body 转换（POST/PUT/PATCH）
   - Query String 转换（所有方法）
2. 响应：将后端返回的 snake_case 数据转换为 camelCase

注意：SSE 流式响应 (text/event-stream) 不做转换，直接透传。
"""
import json
import logging
from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import parse_qs, urlencode

from fastapi.routing import APIRoute
from starlette.routing import Match
from starlette.types import ASGIApp, Receive, Scope, Send, Message

from ..utils.case_converter import to_snake_case, to_camel_case, camel_to_snake
from ..utils.log_sanitization import summarize_query_for_log, summarize_text_for_log

logger = logging.getLogger(__name__)

CASE_CONVERSION_META_ATTR = "__case_conversion_options__"

# Response bodies larger than this many bytes are streamed through WITHOUT
# snake_case -> camelCase conversion. Converting requires buffering the entire
# JSON body in memory and re-serializing it; for very large endpoints (bulk
# exports, large history dumps, file listings) that doubles memory and adds
# latency for no real client benefit. Endpoints returning oversized JSON should
# either fit the camelCase contract on the server side or be exempted; this
# threshold is a conservative safety valve, not the normal path.
MAX_RESPONSE_CONVERSION_BYTES = 2 * 1024 * 1024  # 2 MiB


@dataclass(frozen=True)
class CaseConversionOptions:
    skip_request_body: bool = False
    skip_query: bool = False
    skip_response_body: bool = False
    # When True, this endpoint is ALWAYS converted snake_case -> camelCase even if
    # its JSON body exceeds MAX_RESPONSE_CONVERSION_BYTES. Use for app-owned,
    # unpaginated endpoints whose response can grow past the 2 MiB safety valve
    # (e.g. /sessions, /api/agents) — otherwise they would pass through as
    # snake_case and force the frontend to handle case conversion.
    always_convert_response: bool = False

    @classmethod
    def from_endpoint(cls, endpoint: Any) -> "CaseConversionOptions":
        raw = getattr(endpoint, CASE_CONVERSION_META_ATTR, None)
        if not isinstance(raw, dict):
            return cls()
        return cls(
            skip_request_body=bool(raw.get("skip_request_body", False)),
            skip_query=bool(raw.get("skip_query", False)),
            skip_response_body=bool(raw.get("skip_response_body", False)),
            always_convert_response=bool(raw.get("always_convert_response", False)),
        )


def case_conversion_options(
    *,
    skip_request_body: bool = False,
    skip_query: bool = False,
    skip_response_body: bool = False,
    always_convert_response: bool = False,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Endpoint 元数据：声明是否跳过 case conversion 的某一部分，或强制总是转换响应。

    使用方式：
        @router.post("/upload-from-url")
        @case_conversion_options(skip_request_body=True)
        async def upload_from_url(...):
            ...

        @router.get("/sessions")
        @case_conversion_options(always_convert_response=True)  # 永不因 >2MiB 透传 snake
        async def get_sessions(...):
            ...
    """
    options = {
        "skip_request_body": skip_request_body,
        "skip_query": skip_query,
        "skip_response_body": skip_response_body,
        "always_convert_response": always_convert_response,
    }

    def decorator(endpoint: Callable[..., Any]) -> Callable[..., Any]:
        setattr(endpoint, CASE_CONVERSION_META_ATTR, options)
        return endpoint

    return decorator


class CaseConversionMiddleware:
    """
    数据格式转换中间件（ASGI 原生实现）

    请求转换：
      - JSON body：对 POST/PUT/PATCH 请求进行 camelCase -> snake_case 转换
      - Query String：对所有请求进行 camelCase -> snake_case 转换
    响应转换：
      - 只对 application/json 响应进行 snake_case -> camelCase 转换
      - SSE (text/event-stream) 响应直接透传
    """

    def __init__(self, app: ASGIApp):
        self.app = app
        # 路由 → CaseConversionOptions 缓存，避免每次请求遍历所有路由
        self._route_options_cache: dict[str, CaseConversionOptions] = {}
        self._cache_built = False

    def _build_route_cache(self, app_obj: Any) -> None:
        """启动时一次性构建所有路由的 CaseConversionOptions 映射"""
        if self._cache_built:
            return
        routes = getattr(getattr(app_obj, "router", None), "routes", None)
        if routes is None:
            routes = getattr(app_obj, "routes", [])
        for route in routes:
            if not isinstance(route, APIRoute):
                continue
            opts = CaseConversionOptions.from_endpoint(route.endpoint)
            self._route_options_cache[route.path] = opts
        self._cache_built = True

    def _resolve_case_options(self, scope: Scope) -> CaseConversionOptions:
        app_obj = scope.get("app")
        if app_obj is None:
            return CaseConversionOptions()

        # 首次请求时构建缓存
        if not self._cache_built:
            self._build_route_cache(app_obj)

        path = scope.get("path", "")

        # 快速路径：精确匹配缓存
        if path in self._route_options_cache:
            return self._route_options_cache[path]

        # 慢速路径：含路径参数的路由需要遍历匹配，匹配后缓存实际 path
        routes = getattr(getattr(app_obj, "router", None), "routes", None)
        if routes is None:
            routes = getattr(app_obj, "routes", [])

        for route in routes:
            if not isinstance(route, APIRoute):
                continue
            try:
                match, _ = route.matches(scope)
            except Exception:
                logger.debug("[CaseConversion] Route match probe failed", exc_info=True)
                continue
            if match is Match.FULL:
                opts = CaseConversionOptions.from_endpoint(route.endpoint)
                self._route_options_cache[path] = opts
                return opts

        # 未匹配路由也缓存，避免重复遍历
        default_opts = CaseConversionOptions()
        self._route_options_cache[path] = default_opts
        return default_opts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET")
        options = self._resolve_case_options(scope)

        # ========== Query String 转换 ==========
        query_string = scope.get("query_string", b"")
        if query_string and not options.skip_query:
            try:
                # 解码 Query String：sessionId=123&userId=456
                query_str = query_string.decode("utf-8")

                # 解析为字典（保留空值和多值）
                params = parse_qs(query_str, keep_blank_values=True)

                # 转换键名：sessionId -> session_id
                converted_params = {
                    camel_to_snake(key): value
                    for key, value in params.items()
                }

                # 重新编码：session_id=123&user_id=456
                scope["query_string"] = urlencode(converted_params, doseq=True).encode("utf-8")

                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(
                        "[CaseConversion] Query converted: before=%s after=%s",
                        summarize_query_for_log(query_str),
                        summarize_query_for_log(scope["query_string"]),
                    )
            except Exception as e:
                logger.error(
                    "[CaseConversion] Query String conversion failed: %s",
                    summarize_text_for_log(e, label="error"),
                )

        # ========== 请求处理 ==========
        request_content_type = ""
        for name, value in scope.get("headers", []):
            if name == b"content-type":
                request_content_type = value.decode() if isinstance(value, bytes) else value
                break

        is_json_request = "application/json" in request_content_type
        should_convert_request = (
            method in ["POST", "PUT", "PATCH"]
            and is_json_request
            and not options.skip_request_body
        )

        modified_receive = receive

        if should_convert_request:
            # 一次性读取请求体（FastAPI/Starlette 的请求体通常很小且一次性发送）
            first_message = await receive()
            
            if first_message["type"] == "http.request":
                body = first_message.get("body", b"")
                more_body = first_message.get("more_body", False)
                
                # 如果有更多数据，继续收集
                body_chunks = [body] if body else []
                while more_body:
                    msg = await receive()
                    if msg["type"] == "http.request":
                        chunk = msg.get("body", b"")
                        if chunk:
                            body_chunks.append(chunk)
                        more_body = msg.get("more_body", False)
                    else:
                        break
                
                original_body = b"".join(body_chunks)
                converted_body = original_body

                if original_body:
                    try:
                        data = json.loads(original_body.decode("utf-8"))
                        converted_data = to_snake_case(data)
                        converted_body = json.dumps(converted_data, ensure_ascii=False).encode("utf-8")
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        pass
                    except Exception as e:
                        logger.error(
                            "[CaseConversion] Request conversion failed: %s",
                            summarize_text_for_log(e, label="error"),
                        )

                # 创建新的 receive 函数
                request_sent = False

                async def converted_receive() -> Message:
                    nonlocal request_sent
                    if not request_sent:
                        request_sent = True
                        return {"type": "http.request", "body": converted_body, "more_body": False}
                    # 后续调用：等待原始 receive（用于检测客户端断开）
                    # 这对于 SSE 流式响应很重要
                    return await receive()

                modified_receive = converted_receive
            else:
                # 非 http.request 消息：一次性返回 first_message，后续委托原始 receive
                # 与 converted_receive 保持同样的一次性模式，确保后续调用（如断开检测）
                # 能正确委托到原始 receive，而不是永远重播 first_message。
                passthrough_sent = False

                async def passthrough_receive() -> Message:
                    nonlocal passthrough_sent
                    if not passthrough_sent:
                        passthrough_sent = True
                        return first_message
                    # 后续调用：等待原始 receive（用于检测客户端断开）
                    return await receive()

                modified_receive = passthrough_receive

        # ========== 响应处理 ==========
        is_passthrough = False
        cached_start_message = None
        response_body_chunks: list = []
        response_body_size = 0
        start_flushed = False

        def _content_length_from_headers(headers: Any) -> int | None:
            for name, value in headers or []:
                name_str = name.decode() if isinstance(name, bytes) else name
                if name_str.lower() == "content-length":
                    raw = value.decode() if isinstance(value, bytes) else value
                    try:
                        return int(str(raw).strip())
                    except (TypeError, ValueError):
                        return None
            return None

        async def _flush_buffer_as_passthrough() -> None:
            """
            Abort conversion and stream what we have so far verbatim. Used when a
            JSON body grows past MAX_RESPONSE_CONVERSION_BYTES so we never buffer
            or re-serialize an oversized payload. Original Content-Length (if any)
            is preserved because the bytes are unchanged.
            """
            nonlocal is_passthrough, start_flushed
            is_passthrough = True
            if cached_start_message is not None and not start_flushed:
                start_flushed = True
                await send(cached_start_message)
            for chunk in response_body_chunks:
                if chunk:
                    await send({
                        "type": "http.response.body",
                        "body": chunk,
                        "more_body": True,
                    })
            response_body_chunks.clear()

        async def _emit_converted_response() -> None:
            """Convert the fully-buffered JSON body snake_case -> camelCase and
            send the (re-)framed response. Only called for sub-threshold JSON."""
            full_body = b"".join(response_body_chunks)
            new_body = full_body

            if full_body:
                try:
                    data = json.loads(full_body.decode("utf-8"))
                    converted_data = to_camel_case(data)
                    new_body = json.dumps(converted_data, ensure_ascii=False).encode("utf-8")
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    # Body declared application/json but is not decodable JSON (truncated
                    # stream, mislabeled content-type, binary). Pass the original bytes
                    # through UNCHANGED — converting is impossible and corrupting is worse
                    # — but LOG it so this otherwise-invisible skip is observable instead
                    # of a silent failure that strands the frontend with snake_case.
                    logger.warning(
                        "[CaseConversion] Skipped response conversion: body declared "
                        "application/json but failed to decode (%s)",
                        e,
                    )
                except Exception as e:
                    logger.error(
                        "[CaseConversion] Response conversion failed: %s",
                        summarize_text_for_log(e, label="error"),
                    )

            # 发送响应头（更新 Content-Length）
            if cached_start_message:
                new_headers = []
                for key, value in cached_start_message.get("headers", []):
                    key_str = key.decode() if isinstance(key, bytes) else key
                    if key_str.lower() != "content-length":
                        new_headers.append((key, value))
                new_headers.append((b"content-length", str(len(new_body)).encode()))

                await send({
                    "type": "http.response.start",
                    "status": cached_start_message["status"],
                    "headers": new_headers,
                })

            await send({
                "type": "http.response.body",
                "body": new_body,
                "more_body": False,
            })

        async def send_wrapper(message: Message) -> None:
            nonlocal is_passthrough, cached_start_message, response_body_chunks
            nonlocal response_body_size, start_flushed

            msg_type = message["type"]

            if msg_type == "http.response.start":
                resp_content_type = ""
                for name, value in message.get("headers", []):
                    name_str = name.decode() if isinstance(name, bytes) else name
                    if name_str.lower() == "content-type":
                        resp_content_type = value.decode() if isinstance(value, bytes) else value
                        break

                is_sse = "text/event-stream" in resp_content_type
                is_json = "application/json" in resp_content_type

                # SSE / 非 JSON / endpoint 显式跳过：直接透传
                if is_sse or not is_json or options.skip_response_body:
                    is_passthrough = True
                    start_flushed = True
                    await send(message)
                    return

                # JSON 响应：若声明的 Content-Length 超过阈值，直接透传，
                # 不缓冲、不转换，避免大端点全量驻留内存。
                # always_convert_response 端点豁免此透传：它们必须始终 camelCase
                # （app 自有、无分页的大端点，前端无法处理 snake_case）。
                declared_length = _content_length_from_headers(message.get("headers", []))
                if (
                    not options.always_convert_response
                    and declared_length is not None
                    and declared_length > MAX_RESPONSE_CONVERSION_BYTES
                ):
                    is_passthrough = True
                    start_flushed = True
                    await send(message)
                    return

                # JSON 响应：缓存等待转换
                is_passthrough = False
                cached_start_message = message
                return

            if msg_type == "http.response.body":
                if is_passthrough:
                    await send(message)
                    return

                # JSON 响应：收集并转换
                body = message.get("body", b"")
                more_body = message.get("more_body", False)
                if body:
                    response_body_chunks.append(body)
                    response_body_size += len(body)

                # 累计字节超过阈值（未声明长度的分块响应）：切换为透传，
                # 把已缓冲数据原样下发，后续块流式透传，避免全量缓冲大响应。
                # always_convert_response 端点豁免：继续缓冲并转换。
                if (
                    not options.always_convert_response
                    and response_body_size > MAX_RESPONSE_CONVERSION_BYTES
                ):
                    await _flush_buffer_as_passthrough()
                    if not more_body:
                        await send({
                            "type": "http.response.body",
                            "body": b"",
                            "more_body": False,
                        })
                    return

                if not more_body:
                    await _emit_converted_response()
                return

            # 其他消息直接透传
            await send(message)

        await self.app(scope, modified_receive, send_wrapper)
