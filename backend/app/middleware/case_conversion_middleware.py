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

logger = logging.getLogger(__name__)

CASE_CONVERSION_META_ATTR = "__case_conversion_options__"


@dataclass(frozen=True)
class CaseConversionOptions:
    skip_request_body: bool = False
    skip_query: bool = False
    skip_response_body: bool = False

    @classmethod
    def from_endpoint(cls, endpoint: Any) -> "CaseConversionOptions":
        raw = getattr(endpoint, CASE_CONVERSION_META_ATTR, None)
        if not isinstance(raw, dict):
            return cls()
        return cls(
            skip_request_body=bool(raw.get("skip_request_body", False)),
            skip_query=bool(raw.get("skip_query", False)),
            skip_response_body=bool(raw.get("skip_response_body", False)),
        )


def case_conversion_options(
    *,
    skip_request_body: bool = False,
    skip_query: bool = False,
    skip_response_body: bool = False,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Endpoint 元数据：声明是否跳过 case conversion 的某一部分。

    使用方式：
        @router.post("/upload-from-url")
        @case_conversion_options(skip_request_body=True)
        async def upload_from_url(...):
            ...
    """
    options = {
        "skip_request_body": skip_request_body,
        "skip_query": skip_query,
        "skip_response_body": skip_response_body,
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

    @staticmethod
    def _resolve_case_options(scope: Scope) -> CaseConversionOptions:
        app_obj = scope.get("app")
        if app_obj is None:
            return CaseConversionOptions()

        routes = getattr(getattr(app_obj, "router", None), "routes", None)
        if routes is None:
            routes = getattr(app_obj, "routes", [])

        for route in routes:
            if not isinstance(route, APIRoute):
                continue
            try:
                match, _ = route.matches(scope)
            except Exception:
                continue
            if match is Match.FULL:
                return CaseConversionOptions.from_endpoint(route.endpoint)

        return CaseConversionOptions()

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
                    logger.debug(f"[CaseConversion] Query: {query_str} -> {scope['query_string'].decode('utf-8')}")
            except Exception as e:
                logger.error(f"[CaseConversion] Query String conversion failed: {e}")

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
                        logger.error(f"[CaseConversion] Request conversion failed: {e}")

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
                # 非 http.request 消息，创建透传
                async def passthrough_receive() -> Message:
                    return first_message
                modified_receive = passthrough_receive

        # ========== 响应处理 ==========
        is_passthrough = False
        cached_start_message = None
        response_body_chunks = []

        async def send_wrapper(message: Message) -> None:
            nonlocal is_passthrough, cached_start_message, response_body_chunks

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
                    await send(message)
                else:
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
                if body:
                    response_body_chunks.append(body)

                if not message.get("more_body", False):
                    full_body = b"".join(response_body_chunks)
                    new_body = full_body

                    if full_body:
                        try:
                            data = json.loads(full_body.decode("utf-8"))
                            converted_data = to_camel_case(data)
                            new_body = json.dumps(converted_data, ensure_ascii=False).encode("utf-8")
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            pass
                        except Exception as e:
                            logger.error(f"[CaseConversion] Response conversion failed: {e}")

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
                            "headers": new_headers
                        })

                    await send({
                        "type": "http.response.body",
                        "body": new_body,
                        "more_body": False
                    })
                return

            # 其他消息直接透传
            await send(message)

        await self.app(scope, modified_receive, send_wrapper)
