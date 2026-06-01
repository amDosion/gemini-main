#!/usr/bin/env python3
"""Run OpenAI image/PDF UI E2E checks against the real frontend.

The test starts a minimal fake backend on the same port used by Vite's /api
proxy, drives Firefox through the real UI, and asserts that UI choices reach the
unified mode routes.

The real backend must not be bound to --backend-port while this test runs.
"""

from __future__ import annotations

import argparse
import base64
import json
import socket
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARTIFACT_DIR = REPO_ROOT / "tmp" / "e2e-artifacts" / "openai-image-ui"
TINY_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="
)
MINIMAL_PDF = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >>
endobj
trailer
<< /Root 1 0 R >>
%%EOF
"""


GPT_IMAGE_MODEL = {
    "id": "gpt-image-2",
    "name": "Gpt Image 2",
    "description": "OpenAI image generation model",
    "capabilities": {"vision": True, "search": False, "reasoning": False, "coding": False},
    "contextWindow": 128000,
}
GPT_TEXT_MODEL = {
    "id": "gpt-5.4-mini",
    "name": "GPT 5.4 Mini",
    "description": "OpenAI text and prompt enhancement model",
    "capabilities": {"vision": True, "search": False, "reasoning": True, "coding": False},
    "traits": {"thinking": True},
    "contextWindow": 128000,
}
MODE_CATALOG = [
    {
        "id": "chat",
        "label": "Chat",
        "description": "Chat",
        "hasModels": True,
        "availableModelCount": 1,
        "visibleInNavigation": True,
    },
    {
        "id": "image-gen",
        "label": "Gen",
        "description": "Image generation",
        "hasModels": True,
        "availableModelCount": 1,
        "visibleInNavigation": True,
    },
    {
        "id": "image-chat-edit",
        "label": "Chat Edit",
        "description": "Image edit",
        "hasModels": True,
        "availableModelCount": 1,
        "visibleInNavigation": True,
    },
    {
        "id": "pdf-extract",
        "label": "PDF Extract",
        "description": "PDF extraction",
        "hasModels": True,
        "availableModelCount": 1,
        "visibleInNavigation": True,
    },
]


def _control_schema(mode: str, model_id: str | None) -> dict[str, Any]:
    schema_mode = "image-chat-edit" if mode in {"image-edit", "image-chat-edit"} else mode
    return {
        "schemaVersion": "e2e-openai-image-v1",
        "provider": "openai",
        "mode": schema_mode,
        "requestedMode": mode,
        "modelId": model_id or "gpt-image-2",
        "defaults": {
            "aspect_ratio": "1:1",
            "resolution": "1K",
            "quality": "auto",
            "background": "auto",
            "moderation": "auto",
            "output_format": "png",
            "output_compression_quality": 100,
        },
        "constraints": {"max_image_count": 4},
        "aspectRatios": [
            {"label": "1:1", "value": "1:1"},
            {"label": "3:4", "value": "3:4"},
            {"label": "4:3", "value": "4:3"},
            {"label": "16:9", "value": "16:9"},
            {"label": "9:16", "value": "9:16"},
        ],
        "resolutionTiers": [
            {"label": "1K", "value": "1K", "baseResolution": "1K"},
            {"label": "2K", "value": "2K", "baseResolution": "2K"},
            {"label": "4K", "value": "4K", "baseResolution": "4K"},
        ],
        "resolutionMap": {
            "1K": {"1:1": "1024*1024", "3:4": "1024*1536", "4:3": "1536*1024", "16:9": "1536*864", "9:16": "864*1536"},
            "2K": {"1:1": "2048*2048", "3:4": "2048*3072", "4:3": "3072*2048", "16:9": "3072*1728", "9:16": "1728*3072"},
            "4K": {"1:1": "4096*4096", "3:4": "3072*4096", "4:3": "4096*3072", "16:9": "4096*2304", "9:16": "2304*4096"},
        },
        "paramOptions": {
            "number_of_images": [
                {"label": "1", "value": 1},
                {"label": "2", "value": 2},
                {"label": "3", "value": 3},
                {"label": "4", "value": 4},
            ],
            "openai_image_api": [
                {"label": "Image API", "value": "image"},
                {"label": "Responses API", "value": "responses"},
            ],
        },
    }


class FakeOpenAIBackend(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int]):
        super().__init__(server_address, FakeOpenAIBackendHandler)
        self.captured: list[dict[str, Any]] = []
        self.unhandled: list[dict[str, Any]] = []
        self.sessions: dict[str, dict[str, Any]] = {}
        self.lock = threading.Lock()

    def append_capture(self, item: dict[str, Any]) -> None:
        with self.lock:
            self.captured.append(item)

    def captures_since(self, offset: int) -> list[dict[str, Any]]:
        with self.lock:
            return list(self.captured[offset:])

    def capture_count(self) -> int:
        with self.lock:
            return len(self.captured)


class FakeOpenAIBackendHandler(BaseHTTPRequestHandler):
    server: FakeOpenAIBackend

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send_json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "authorization,content-type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,PATCH,DELETE,OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def _send_png(self) -> None:
        body = base64.b64decode(TINY_PNG_BASE64)
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "public, max-age=3600")
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> Any:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return None
        raw = self.rfile.read(length)
        content_type = self.headers.get("Content-Type", "")
        if "application/json" not in content_type:
            return {"_rawLength": len(raw), "_contentType": content_type}
        return json.loads(raw.decode("utf-8"))

    def _parsed(self) -> urllib.parse.ParseResult:
        return urllib.parse.urlparse(self.path)

    def do_OPTIONS(self) -> None:
        self._send_json(204, {})

    def do_GET(self) -> None:
        parsed = self._parsed()
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path == "/health":
            self._send_json(200, {"status": "ok", "fake": True})
            return
        if path.startswith("/api/storage/local-files/e2e/"):
            self._send_png()
            return
        if path == "/api/auth/config":
            self._send_json(200, {"allowRegistration": True})
            return
        if path == "/api/auth/me":
            self._send_json(200, {
                "id": "e2e-user",
                "email": "e2e@example.com",
                "name": "OpenAI E2E",
                "status": "active",
                "hasActiveProfile": True,
            })
            return
        if path == "/api/init/critical":
            profile = {
                "id": "profile-openai-e2e",
                "name": "OpenAI E2E",
                "providerId": "openai",
                "apiKey": "sk-e2e",
                "baseUrl": "https://api.openai.invalid/v1",
                "protocol": "openai",
                "isProxy": False,
                "hiddenModels": [],
                "savedModels": [GPT_IMAGE_MODEL, GPT_TEXT_MODEL],
                "createdAt": 1779620000000,
                "updatedAt": 1779620000000,
            }
            self._send_json(200, {
                "profiles": [profile],
                "activeProfileId": profile["id"],
                "activeProfile": profile,
                "dashscopeKey": "",
                "cachedModels": [GPT_IMAGE_MODEL, GPT_TEXT_MODEL],
                "cachedModeCatalog": MODE_CATALOG,
                "cachedChatModels": [GPT_TEXT_MODEL],
                "cachedDefaultModelId": GPT_TEXT_MODEL["id"],
            })
            return
        if path == "/api/init/non-critical":
            self._send_json(200, {
                "sessions": [],
                "sessionsMode": "chat",
                "sessionsTotal": 0,
                "sessionsHasMore": False,
                "personas": [],
                "storageConfigs": [],
                "activeStorageId": None,
                "imagenConfig": None,
            })
            return
        if path == "/api/init/sessions/more":
            self._send_json(200, {"sessions": [], "total": 0, "hasMore": False, "nextCursor": None})
            return
        if path == "/api/sessions":
            with self.server.lock:
                sessions = list(self.server.sessions.values())
            self._send_json(200, sessions)
            return
        if path.startswith("/api/sessions/"):
            session_id = urllib.parse.unquote(path.removeprefix("/api/sessions/"))
            with self.server.lock:
                session = self.server.sessions.get(session_id)
            if session:
                self._send_json(200, session)
            else:
                self._send_json(200, {
                    "id": session_id,
                    "title": "E2E Session",
                    "messages": [],
                    "createdAt": int(time.time() * 1000),
                    "mode": "chat",
                })
            return
        if path == "/api/providers/templates":
            self._send_json(200, [{
                "id": "openai",
                "name": "OpenAI",
                "protocol": "openai",
                "baseUrl": "https://api.openai.invalid/v1",
                "defaultModel": GPT_TEXT_MODEL["id"],
                "description": "OpenAI fake provider for UI e2e",
                "capabilities": {"vision": True, "thinking": True},
                "modes": ["chat", "image-gen", "image-chat-edit", "pdf-extract"],
            }])
            return
        if path == "/api/models/openai":
            mode = (query.get("mode") or [""])[0]
            if mode in {"image-gen", "image-chat-edit"}:
                models = [GPT_IMAGE_MODEL]
                default_model_id = GPT_IMAGE_MODEL["id"]
            elif mode == "pdf-extract" or mode == "chat":
                models = [GPT_TEXT_MODEL]
                default_model_id = GPT_TEXT_MODEL["id"]
            else:
                models = [GPT_IMAGE_MODEL, GPT_TEXT_MODEL]
                default_model_id = GPT_TEXT_MODEL["id"]
            self._send_json(200, {
                "models": models,
                "defaultModelId": default_model_id,
                "modeCatalog": MODE_CATALOG,
                "filteredByMode": mode or None,
                "cached": False,
                "provider": "openai",
            })
            return
        if path.startswith("/api/modes/openai/") and path.endswith("/controls"):
            mode = path.removeprefix("/api/modes/openai/").removesuffix("/controls")
            model_id = (query.get("model_id") or [None])[0]
            self._send_json(200, {
                "success": True,
                "provider": "openai",
                "mode": mode,
                "modelId": model_id,
                "schema": _control_schema(mode, model_id),
            })
            return
        if path == "/api/pdf/templates":
            self._send_json(200, {
                "success": True,
                "templates": [
                    {"id": "invoice", "name": "Invoice", "description": "Extract invoice details", "icon": "PDF"},
                    {"id": "form", "name": "Form", "description": "Extract form fields", "icon": "FORM"},
                ],
            })
            return
        if path == "/api/storage/configs":
            self._send_json(200, [])
            return

        with self.server.lock:
            self.server.unhandled.append({"method": "GET", "path": self.path})
        self._send_json(404, {"detail": f"Unhandled fake backend GET {self.path}"})

    def do_POST(self) -> None:
        parsed = self._parsed()
        path = parsed.path
        body = self._read_json_body()

        if path == "/api/auth/refresh":
            self._send_json(200, {
                "accessToken": "e2e-access-token",
                "refreshToken": "e2e-refresh-token",
                "hasActiveProfile": True,
            })
            return
        if path == "/api/sessions":
            if isinstance(body, dict) and body.get("id"):
                with self.server.lock:
                    self.server.sessions[str(body["id"])] = body
            self._send_json(200, {"success": True})
            return
        if path == "/api/storage/upload-async":
            query = urllib.parse.parse_qs(parsed.query)
            self._send_json(200, {
                "taskId": "upload-task-e2e",
                "attachmentId": (query.get("attachmentId") or ["attachment-e2e"])[0],
                "status": "pending",
                "enqueued": True,
                "queuePosition": 1,
            })
            return
        if path.startswith("/api/modes/openai/"):
            mode = path.removeprefix("/api/modes/openai/")
            self.server.append_capture({"path": path, "mode": mode, "body": body})
            if mode in {"image-gen", "image-chat-edit"}:
                options = (body or {}).get("options") or {}
                count = int(options.get("numberOfImages") or 1)
                images = [
                    {
                        "url": f"/api/storage/local-files/e2e/{mode}-{index + 1}.png",
                        "mimeType": "image/png",
                        "filename": f"{mode}-{index + 1}.png",
                        "attachmentId": f"{mode}-attachment-{index + 1}",
                        "uploadStatus": "completed",
                        "openaiResponseId": "resp_e2e_123",
                        "messageId": options.get("messageId"),
                        "sessionId": options.get("sessionId") or options.get("frontendSessionId"),
                        "enhancedPrompt": "E2E enhanced prompt",
                    }
                    for index in range(max(1, min(count, 4)))
                ]
                self._send_json(200, {"success": True, "data": {"images": images}})
                return
            if mode == "pdf-extract":
                options = (body or {}).get("options") or {}
                template = options.get("pdfExtractTemplate") or "invoice"
                self._send_json(200, {
                    "success": True,
                    "data": {
                        "success": True,
                        "templateType": template,
                        "templateName": "Form" if template == "form" else "Invoice",
                        "data": {"field": "e2e", "total": "12.34"},
                        "rawText": "fake pdf text",
                    },
                })
                return

        with self.server.lock:
            self.server.unhandled.append({"method": "POST", "path": self.path, "body": body})
        self._send_json(404, {"detail": f"Unhandled fake backend POST {self.path}"})


def _port_is_free(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def _start_fake_backend(host: str, port: int) -> FakeOpenAIBackend:
    if not _port_is_free(host, port):
        raise RuntimeError(
            f"Port {port} is already in use. Stop the real backend before running this E2E test."
        )
    server = FakeOpenAIBackend((host, port))
    thread = threading.Thread(target=server.serve_forever, name="fake-openai-backend", daemon=True)
    thread.start()
    return server


def _wait_for_url(url: str, timeout_seconds: int) -> None:
    deadline = time.time() + timeout_seconds
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status < 500:
                    return
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
        time.sleep(0.5)
    raise RuntimeError(f"Timed out waiting for {url}: {last_error}")


def _visible(driver: webdriver.Firefox, by: str, selector: str):
    for element in driver.find_elements(by, selector):
        if element.is_displayed():
            return element
    return None


def _wait_visible(driver: webdriver.Firefox, wait: WebDriverWait, by: str, selector: str):
    return wait.until(lambda drv: _visible(drv, by, selector))


def _css_attr(name: str, value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'[{name}="{escaped}"]'


def _xpath_literal(value: str) -> str:
    if "'" not in value:
        return f"'{value}'"
    if '"' not in value:
        return f'"{value}"'
    parts = value.split("'")
    return "concat(" + ', "\'", '.join(f"'{part}'" for part in parts) + ")"


def _click_visible_button(driver: webdriver.Firefox, wait: WebDriverWait, label: str) -> None:
    literal = _xpath_literal(label)
    xpath = f"//button[normalize-space()={literal} or .//span[normalize-space()={literal}]]"

    def find_button(drv: webdriver.Firefox):
        for button in drv.find_elements(By.XPATH, xpath):
            if button.is_displayed() and button.is_enabled():
                return button
        return None

    button = wait.until(find_button)
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
    button.click()


def _set_control_value(driver: webdriver.Firefox, element, value: str) -> None:
    driver.execute_script(
        """
        const element = arguments[0];
        const value = arguments[1];
        const setter = Object.getOwnPropertyDescriptor(element.__proto__, 'value')?.set;
        if (setter) setter.call(element, value);
        else element.value = value;
        element.dispatchEvent(new Event('input', { bubbles: true }));
        element.dispatchEvent(new Event('change', { bubbles: true }));
        """,
        element,
        value,
    )


def _select_value(driver: webdriver.Firefox, wait: WebDriverWait, aria_label: str, value: str) -> None:
    selector = f"select{_css_attr('aria-label', aria_label)}"
    select = _wait_visible(driver, wait, By.CSS_SELECTOR, selector)
    wait.until(lambda _drv: any(option.get_attribute("value") == value for option in select.find_elements(By.TAG_NAME, "option")))
    Select(select).select_by_value(value)
    wait.until(lambda _drv: select.get_attribute("value") == value)


def _set_range_value(driver: webdriver.Firefox, wait: WebDriverWait, aria_label: str, value: int) -> None:
    selector = f"input[type='range']{_css_attr('aria-label', aria_label)}"
    element = _wait_visible(driver, wait, By.CSS_SELECTOR, selector)
    _set_control_value(driver, element, str(value))
    wait.until(lambda _drv: element.get_attribute("value") == str(value))


def _ensure_switch(driver: webdriver.Firefox, wait: WebDriverWait, label: str, checked: bool) -> None:
    selector = f"button[role='switch']{_css_attr('aria-label', label)}"
    button = _wait_visible(driver, wait, By.CSS_SELECTOR, selector)
    current = button.get_attribute("aria-checked") == "true"
    if current != checked:
        button.click()
        wait.until(lambda _drv: button.get_attribute("aria-checked") == ("true" if checked else "false"))


def _active_file_input(driver: webdriver.Firefox, wait: WebDriverWait, selector: str):
    def find_input(drv: webdriver.Firefox):
        for element in drv.find_elements(By.CSS_SELECTOR, selector):
            active_ancestor = drv.execute_script(
                """
                let node = arguments[0].parentElement;
                while (node) {
                  const style = window.getComputedStyle(node);
                  if (style.display === 'none' || style.visibility === 'hidden') return false;
                  node = node.parentElement;
                }
                return true;
                """,
                element,
            )
            if active_ancestor:
                return element
        return None

    element = wait.until(find_input)
    driver.execute_script(
        """
        arguments[0].classList.remove('hidden');
        arguments[0].style.display = 'block';
        arguments[0].style.position = 'fixed';
        arguments[0].style.left = '0';
        arguments[0].style.top = '0';
        arguments[0].style.width = '1px';
        arguments[0].style.height = '1px';
        arguments[0].style.opacity = '0.01';
        """,
        element,
    )
    return element


def _wait_capture(server: FakeOpenAIBackend, mode: str, offset: int, timeout_seconds: int) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        for item in server.captures_since(offset):
            if item.get("mode") == mode:
                return item
        time.sleep(0.2)
    raise TimeoutError(f"Timed out waiting for captured {mode} request")


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _make_test_files(tmp_dir: Path) -> tuple[Path, Path]:
    image_path = tmp_dir / "openai-e2e-source.png"
    image_path.write_bytes(base64.b64decode(TINY_PNG_BASE64))
    pdf_path = tmp_dir / "openai-e2e.pdf"
    pdf_path.write_bytes(MINIMAL_PDF)
    return image_path, pdf_path


def _inject_auth(driver: webdriver.Firefox, base_url: str) -> None:
    driver.get(base_url)
    driver.execute_script(
        """
        localStorage.clear();
        localStorage.setItem('access_token', 'e2e-access-token');
        localStorage.setItem('refresh_token', 'e2e-refresh-token');
        localStorage.setItem('has_active_profile', 'true');
        """
    )


def run(args: argparse.Namespace) -> dict[str, Any]:
    artifact_dir = Path(args.artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    _wait_for_url(args.base_url, args.frontend_timeout_seconds)
    server = _start_fake_backend(args.backend_host, args.backend_port)

    options = Options()
    if args.headless:
        options.add_argument("-headless")
    options.set_preference("dom.webnotifications.enabled", False)

    result: dict[str, Any] = {
        "status": "started",
        "base_url": args.base_url,
        "backend_port": args.backend_port,
        "captures": [],
    }
    driver = webdriver.Firefox(options=options)
    try:
        driver.set_window_size(args.width, args.height)
        wait = WebDriverWait(driver, args.ui_timeout_seconds)
        with tempfile.TemporaryDirectory(prefix="openai-image-ui-e2e-") as tmp:
            image_path, pdf_path = _make_test_files(Path(tmp))

            _inject_auth(driver, args.base_url)
            driver.get(args.base_url)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='app-shell']")))

            before = server.capture_count()
            _click_visible_button(driver, wait, "Gen")
            _wait_visible(driver, wait, By.CSS_SELECTOR, "textarea[placeholder*='描述你想要生成的图片']")
            _click_visible_button(driver, wait, "Responses API")
            _select_value(driver, wait, "Responses 模型", GPT_TEXT_MODEL["id"])
            _set_range_value(driver, wait, "生成数量", 3)
            _ensure_switch(driver, wait, "AI 增强提示词", True)
            _select_value(driver, wait, "增强提示词模型", GPT_TEXT_MODEL["id"])
            _select_value(driver, wait, "思考等级", "high")
            prompt = _wait_visible(driver, wait, By.CSS_SELECTOR, "textarea[placeholder*='描述你想要生成的图片']")
            _set_control_value(driver, prompt, "E2E OpenAI responses image generation")
            _click_visible_button(driver, wait, "生成图片")
            gen_request = _wait_capture(server, "image-gen", before, args.request_timeout_seconds)
            gen_options = gen_request["body"]["options"]
            _assert(gen_request["body"]["modelId"] == GPT_IMAGE_MODEL["id"], "GEN did not use gpt-image-2")
            _assert(gen_options["openaiImageApi"] == "responses", "GEN did not submit Responses API")
            _assert(gen_options["openaiResponsesModel"] == GPT_TEXT_MODEL["id"], "GEN Responses model missing")
            _assert(gen_options["numberOfImages"] == 3, "GEN image count did not come from slider")
            _assert(gen_options["enhancePrompt"] is True, "GEN prompt enhancement not enabled")
            _assert(gen_options["enhancePromptThinkingLevel"] == "high", "GEN thinking level missing")
            wait.until(lambda drv: any(
                img.is_displayed() and (img.get_attribute("alt") or "").startswith("生成图片")
                for img in drv.find_elements(By.TAG_NAME, "img")
            ))
            result["captures"].append({"mode": "image-gen", "options": gen_options})

            before = server.capture_count()
            _click_visible_button(driver, wait, "Chat Edit")
            _wait_visible(driver, wait, By.CSS_SELECTOR, "textarea[placeholder*='请先上传图片']")
            file_input = _active_file_input(driver, wait, "input[type='file'][accept='image/*']")
            file_input.send_keys(str(image_path))
            _wait_visible(driver, wait, By.CSS_SELECTOR, "textarea[placeholder*='描述你要对图片做的编辑']")
            _click_visible_button(driver, wait, "Responses API")
            _select_value(driver, wait, "Responses 模型", GPT_TEXT_MODEL["id"])
            _ensure_switch(driver, wait, "AI 增强提示词", True)
            _select_value(driver, wait, "增强提示词模型", GPT_TEXT_MODEL["id"])
            _select_value(driver, wait, "思考等级", "medium")
            edit_prompt = _wait_visible(driver, wait, By.CSS_SELECTOR, "textarea[placeholder*='描述你要对图片做的编辑']")
            _set_control_value(driver, edit_prompt, "E2E edit the uploaded image")
            _click_visible_button(driver, wait, "开始编辑")
            edit_request = _wait_capture(server, "image-chat-edit", before, args.request_timeout_seconds)
            edit_options = edit_request["body"]["options"]
            _assert(edit_request["body"]["modelId"] == GPT_IMAGE_MODEL["id"], "Chat Edit did not use gpt-image-2")
            _assert(edit_options["openaiImageApi"] == "responses", "Chat Edit did not submit Responses API")
            _assert(edit_options["openaiResponsesModel"] == GPT_TEXT_MODEL["id"], "Chat Edit Responses model missing")
            _assert(len(edit_request["body"].get("attachments") or []) >= 1, "Chat Edit did not send uploaded attachment")
            _assert(edit_options["enhancePromptThinkingLevel"] == "medium", "Chat Edit thinking level missing")
            result["captures"].append({"mode": "image-chat-edit", "options": edit_options})

            before = server.capture_count()
            _click_visible_button(driver, wait, "PDF Extract")
            _wait_visible(driver, wait, By.CSS_SELECTOR, "textarea[placeholder*='请先上传 PDF 文件']")
            pdf_input = _active_file_input(driver, wait, "input[type='file'][accept*='.pdf']")
            pdf_input.send_keys(str(pdf_path))
            _click_visible_button(driver, wait, "Form")
            pdf_prompt = _wait_visible(driver, wait, By.CSS_SELECTOR, "textarea[placeholder*='提取指令']")
            _set_control_value(driver, pdf_prompt, "Extract E2E form fields")
            _click_visible_button(driver, wait, "开始提取")
            pdf_request = _wait_capture(server, "pdf-extract", before, args.request_timeout_seconds)
            pdf_options = pdf_request["body"]["options"]
            _assert(pdf_request["body"]["modelId"] == GPT_TEXT_MODEL["id"], "PDF did not use text model")
            _assert(pdf_options["pdfExtractTemplate"] == "form", "PDF template was not submitted")
            _assert(len(pdf_request["body"].get("attachments") or []) == 1, "PDF attachment was not submitted")
            result["captures"].append({"mode": "pdf-extract", "options": pdf_options})

            driver.save_screenshot(str(artifact_dir / "openai-image-ui-e2e-final.png"))
            result["status"] = "passed"
            return result
    except Exception:
        driver.save_screenshot(str(artifact_dir / "openai-image-ui-e2e-failure.png"))
        raise
    finally:
        driver.quit()
        server.shutdown()
        server.server_close()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:21573/")
    parser.add_argument("--backend-host", default="127.0.0.1")
    parser.add_argument("--backend-port", type=int, default=21574)
    parser.add_argument("--artifact-dir", default=str(DEFAULT_ARTIFACT_DIR))
    parser.add_argument("--width", type=int, default=1440)
    parser.add_argument("--height", type=int, default=1000)
    parser.add_argument("--ui-timeout-seconds", type=int, default=30)
    parser.add_argument("--frontend-timeout-seconds", type=int, default=30)
    parser.add_argument("--request-timeout-seconds", type=int, default=20)
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args()
    args.headless = not args.headed
    return args


if __name__ == "__main__":
    payload = run(parse_args())
    print(json.dumps(payload, ensure_ascii=False, indent=2))
