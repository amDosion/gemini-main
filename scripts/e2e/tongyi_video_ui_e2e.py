#!/usr/bin/env python3
"""Run Tongyi video UI E2E checks against the real frontend and a fake backend.

The test drives the real browser UI through video-gen strategy selection,
attachment role assignment, and submit. It does not call DashScope; the fake
backend captures the unified mode payloads so the test can assert the browser
sent the same contract that the real backend expects.
"""

from __future__ import annotations

import argparse
import base64
import json
import tempfile
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select, WebDriverWait

from openai_image_ui_e2e import (
    TINY_PNG_BASE64,
    _active_file_input,
    _assert,
    _click_visible_button,
    _port_is_free,
    _set_control_value,
    _wait_for_url,
    _wait_visible,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ARTIFACT_DIR = REPO_ROOT / "tmp" / "e2e-artifacts" / "tongyi-video-ui"

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
        "id": "video-gen",
        "label": "Video",
        "description": "Video generation",
        "hasModels": True,
        "availableModelCount": 4,
        "visibleInNavigation": True,
    },
]

VIDEO_MODELS = [
    {
        "id": "wan2.7-i2v",
        "name": "Wan 2.7 I2V",
        "description": "Tongyi image/video to video model",
        "supportedTasks": ["video-gen"],
        "capabilities": {"vision": True, "search": False, "reasoning": False, "coding": False},
    },
    {
        "id": "wan2.7-r2v",
        "name": "Wan 2.7 R2V",
        "description": "Tongyi reference to video model",
        "supportedTasks": ["video-gen"],
        "capabilities": {"vision": True, "search": False, "reasoning": False, "coding": False},
    },
    {
        "id": "wan2.7-videoedit",
        "name": "Wan 2.7 Video Edit",
        "description": "Tongyi video edit model",
        "supportedTasks": ["video-gen"],
        "capabilities": {"vision": True, "search": False, "reasoning": False, "coding": False},
    },
]


def _video_control_schema(model_id: str | None) -> dict[str, Any]:
    return {
        "schemaVersion": "e2e-tongyi-video-v1",
        "provider": "tongyi",
        "mode": "video-gen",
        "requestedMode": "video-gen",
        "modelId": model_id or "wan2.7-i2v",
        "defaults": {
            "aspect_ratio": "16:9",
            "resolution": "720p",
            "seconds": "5",
            "video_input_strategy": "first_frame_to_video",
            "prompt_extend": True,
        },
        "aspectRatios": [
            {"label": "16:9 Landscape", "value": "16:9"},
            {"label": "9:16 Portrait", "value": "9:16"},
        ],
        "resolutionTiers": [
            {"label": "720p HD", "value": "720p", "baseResolution": "1280*720"},
            {"label": "1080p Full HD", "value": "1080p", "baseResolution": "1920*1080"},
            {"label": "4K UHD", "value": "4k", "baseResolution": "3840*2160"},
        ],
        "paramOptions": {
            "seconds": [
                {"label": "5s", "value": "5"},
                {"label": "10s", "value": "10"},
            ],
            "storyboard_shot_seconds": [{"label": "5s", "value": 5}],
        },
        "videoContract": {
            "inputStrategies": [
                {"id": "first_frame_to_video", "label": "首帧生视频", "requires": ["source_image"]},
                {
                    "id": "first_last_frame_to_video",
                    "label": "首尾帧生成",
                    "requires": ["source_image", "last_frame_image"],
                },
                {"id": "video_continuation", "label": "视频续写", "requires": ["source_video"]},
                {"id": "reference_to_video", "label": "参考生视频", "requires": ["reference_images"]},
                {
                    "id": "video_edit",
                    "label": "视频编辑",
                    "requires": ["source_video"],
                    "allows": ["video_edit_reference_images"],
                },
            ],
            "attachmentSlots": [
                {"name": "source_image", "label": "首帧", "kind": "image", "roles": ["first_frame"], "enabled": True},
                {"name": "last_frame_image", "label": "尾帧", "kind": "image", "roles": ["last_frame"], "enabled": True},
                {"name": "source_video", "label": "源视频", "kind": "video", "roles": ["source_video"], "enabled": True},
                {
                    "name": "reference_images",
                    "label": "参考图",
                    "kind": "image",
                    "roles": ["reference_image"],
                    "enabled": True,
                },
                {
                    "name": "video_edit_reference_images",
                    "label": "编辑参考图",
                    "kind": "image",
                    "roles": ["reference_image"],
                    "enabled": True,
                },
                {
                    "name": "driving_audio",
                    "label": "驱动音频",
                    "kind": "audio",
                    "roles": ["driving_audio"],
                    "enabled": True,
                },
            ],
        },
    }


class FakeTongyiBackend(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int]):
        super().__init__(server_address, FakeTongyiBackendHandler)
        self.captured: list[dict[str, Any]] = []
        self.sessions: dict[str, dict[str, Any]] = {}
        self.unhandled: list[dict[str, Any]] = []
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


class FakeTongyiBackendHandler(BaseHTTPRequestHandler):
    server: FakeTongyiBackend

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
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> Any:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return None
        raw = self.rfile.read(length)
        if "application/json" not in self.headers.get("Content-Type", ""):
            return {"_rawLength": len(raw), "_contentType": self.headers.get("Content-Type", "")}
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
                "email": "tongyi-e2e@example.com",
                "name": "Tongyi Video E2E",
                "status": "active",
                "hasActiveProfile": True,
            })
            return
        if path == "/api/init/critical":
            profile = {
                "id": "profile-tongyi-e2e",
                "name": "Tongyi E2E",
                "providerId": "tongyi",
                "apiKey": "dashscope-e2e",
                "baseUrl": "https://dashscope.aliyuncs.invalid/compatible-mode/v1",
                "protocol": "openai",
                "isProxy": False,
                "hiddenModels": [],
                "savedModels": VIDEO_MODELS,
                "createdAt": 1779620000000,
                "updatedAt": 1779620000000,
            }
            self._send_json(200, {
                "profiles": [profile],
                "activeProfileId": profile["id"],
                "activeProfile": profile,
                "cachedModels": VIDEO_MODELS,
                "cachedModeCatalog": MODE_CATALOG,
                "cachedChatModels": [],
                "cachedDefaultModelId": VIDEO_MODELS[0]["id"],
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
            self._send_json(200, session or {
                "id": session_id,
                "title": "Tongyi Video E2E",
                "messages": [],
                "createdAt": int(time.time() * 1000),
                "mode": "video-gen",
            })
            return
        if path == "/api/providers/templates":
            self._send_json(200, [{
                "id": "tongyi",
                "name": "Tongyi",
                "protocol": "openai",
                "baseUrl": "https://dashscope.aliyuncs.invalid/compatible-mode/v1",
                "defaultModel": VIDEO_MODELS[0]["id"],
                "description": "Tongyi fake provider for video UI e2e",
                "capabilities": {"vision": True},
                "modes": ["video-gen"],
            }])
            return
        if path == "/api/models/tongyi":
            self._send_json(200, {
                "models": VIDEO_MODELS,
                "defaultModelId": VIDEO_MODELS[0]["id"],
                "modeCatalog": MODE_CATALOG,
                "filteredByMode": (query.get("mode") or [None])[0],
                "cached": False,
                "provider": "tongyi",
            })
            return
        if path.startswith("/api/modes/tongyi/") and path.endswith("/controls"):
            mode = path.removeprefix("/api/modes/tongyi/").removesuffix("/controls")
            model_id = (query.get("model_id") or [VIDEO_MODELS[0]["id"]])[0]
            self._send_json(200, {
                "success": True,
                "provider": "tongyi",
                "mode": mode,
                "modelId": model_id,
                "schema": _video_control_schema(model_id),
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
        if path == "/api/modes/tongyi/video-gen":
            self.server.append_capture({"path": path, "mode": "video-gen", "body": body})
            options = (body or {}).get("options") or {}
            self._send_json(200, {
                "success": True,
                "data": {
                    "url": "/api/storage/local-files/e2e/tongyi-video.mp4",
                    "mimeType": "video/mp4",
                    "filename": "tongyi-video.mp4",
                    "attachmentId": f"video-{len(self.server.captured)}",
                    "uploadStatus": "completed",
                    "messageId": options.get("messageId"),
                    "sessionId": options.get("sessionId") or options.get("frontendSessionId"),
                    "derivedAssets": [{
                        "kind": "video_last_frame",
                        "role": "last_frame",
                        "url": "/api/storage/local-files/e2e/tongyi-last-frame.png",
                        "attachmentId": f"frame-{len(self.server.captured)}",
                        "mimeType": "image/png",
                        "filename": "tongyi-last-frame.png",
                        "uploadStatus": "completed",
                    }],
                },
            })
            return

        with self.server.lock:
            self.server.unhandled.append({"method": "POST", "path": self.path, "body": body})
        self._send_json(404, {"detail": f"Unhandled fake backend POST {self.path}"})


def _start_fake_backend(host: str, port: int) -> FakeTongyiBackend:
    if not _port_is_free(host, port):
        raise RuntimeError(f"Port {port} is already in use. Stop the real backend before running this E2E test.")
    server = FakeTongyiBackend((host, port))
    thread = threading.Thread(target=server.serve_forever, name="fake-tongyi-backend", daemon=True)
    thread.start()
    return server


def _wait_capture(server: FakeTongyiBackend, offset: int, timeout_seconds: int) -> dict[str, Any]:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        captures = server.captures_since(offset)
        if captures:
            return captures[0]
        time.sleep(0.2)
    raise TimeoutError("Timed out waiting for captured video-gen request")


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


def _make_test_files(tmp_dir: Path) -> tuple[Path, Path, Path]:
    first = tmp_dir / "first-frame.png"
    last = tmp_dir / "last-frame.png"
    source_video = tmp_dir / "source-video.mp4"
    first.write_bytes(base64.b64decode(TINY_PNG_BASE64))
    last.write_bytes(base64.b64decode(TINY_PNG_BASE64))
    source_video.write_bytes(b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom")
    return first, last, source_video


def _upload_files(driver: webdriver.Firefox, wait: WebDriverWait, paths: list[Path]) -> None:
    file_input = _active_file_input(driver, wait, "input[type='file']")
    file_input.send_keys("\n".join(str(path) for path in paths))


def _set_attachment_role(driver: webdriver.Firefox, wait: WebDriverWait, file_name: str, role: str) -> None:
    selector = f"select[aria-label='素材角色 {file_name}']"
    element = _wait_visible(driver, wait, By.CSS_SELECTOR, selector)
    Select(element).select_by_value(role)
    wait.until(lambda _drv: element.get_attribute("value") == role)


def _submit_video_prompt(driver: webdriver.Firefox, wait: WebDriverWait, prompt_text: str) -> None:
    prompt = _wait_visible(driver, wait, By.CSS_SELECTOR, "textarea[placeholder*='描述你想生成的视频']")
    _set_control_value(driver, prompt, prompt_text)
    _click_visible_button(driver, wait, "生成视频")


def _assert_request(capture: dict[str, Any], strategy: str, roles: list[str]) -> None:
    body = capture["body"]
    options = body.get("options") or {}
    attachments = body.get("attachments") or []
    _assert(options.get("videoInputStrategy") == strategy, f"Expected videoInputStrategy={strategy}")
    actual_roles = [attachment.get("role") for attachment in attachments]
    for role in roles:
        _assert(role in actual_roles, f"Expected attachment role {role}, got {actual_roles}")


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
        with tempfile.TemporaryDirectory(prefix="tongyi-video-ui-e2e-") as tmp:
            first_image, last_image, source_video = _make_test_files(Path(tmp))
            _inject_auth(driver, args.base_url)
            driver.get(args.base_url)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='app-shell']")))
            _click_visible_button(driver, wait, "Video")
            _wait_visible(driver, wait, By.CSS_SELECTOR, "textarea[placeholder*='描述你想生成的视频']")

            before = server.capture_count()
            _click_visible_button(driver, wait, "首帧生视频")
            _upload_files(driver, wait, [first_image])
            _submit_video_prompt(driver, wait, "E2E Tongyi first frame to video")
            first_frame_request = _wait_capture(server, before, args.request_timeout_seconds)
            _assert_request(first_frame_request, "first_frame_to_video", ["first_frame"])
            result["captures"].append({
                "strategy": "first_frame_to_video",
                "attachmentRoles": [att.get("role") for att in first_frame_request["body"].get("attachments", [])],
            })

            before = server.capture_count()
            _click_visible_button(driver, wait, "首尾帧生成")
            _upload_files(driver, wait, [first_image, last_image])
            _set_attachment_role(driver, wait, first_image.name, "first_frame")
            _set_attachment_role(driver, wait, last_image.name, "last_frame")
            _submit_video_prompt(driver, wait, "E2E Tongyi first and last frame video")
            first_last_request = _wait_capture(server, before, args.request_timeout_seconds)
            _assert_request(first_last_request, "first_last_frame_to_video", ["first_frame", "last_frame"])
            result["captures"].append({
                "strategy": "first_last_frame_to_video",
                "attachmentRoles": [att.get("role") for att in first_last_request["body"].get("attachments", [])],
            })

            before = server.capture_count()
            _click_visible_button(driver, wait, "视频续写")
            _upload_files(driver, wait, [source_video])
            _set_attachment_role(driver, wait, source_video.name, "source_video")
            _submit_video_prompt(driver, wait, "E2E Tongyi video continuation")
            continuation_request = _wait_capture(server, before, args.request_timeout_seconds)
            _assert_request(continuation_request, "video_continuation", ["source_video"])
            result["captures"].append({
                "strategy": "video_continuation",
                "attachmentRoles": [att.get("role") for att in continuation_request["body"].get("attachments", [])],
            })

            before = server.capture_count()
            _click_visible_button(driver, wait, "参考生视频")
            _upload_files(driver, wait, [first_image])
            _set_attachment_role(driver, wait, first_image.name, "reference_image")
            _submit_video_prompt(driver, wait, "E2E Tongyi reference to video")
            reference_request = _wait_capture(server, before, args.request_timeout_seconds)
            _assert_request(reference_request, "reference_to_video", ["reference_image"])
            result["captures"].append({
                "strategy": "reference_to_video",
                "attachmentRoles": [att.get("role") for att in reference_request["body"].get("attachments", [])],
            })

            before = server.capture_count()
            _click_visible_button(driver, wait, "视频编辑")
            _upload_files(driver, wait, [source_video, first_image])
            _set_attachment_role(driver, wait, source_video.name, "source_video")
            _set_attachment_role(driver, wait, first_image.name, "reference_image")
            _submit_video_prompt(driver, wait, "E2E Tongyi video edit with reference image")
            edit_request = _wait_capture(server, before, args.request_timeout_seconds)
            _assert_request(edit_request, "video_edit", ["source_video", "reference_image"])
            result["captures"].append({
                "strategy": "video_edit",
                "attachmentRoles": [att.get("role") for att in edit_request["body"].get("attachments", [])],
            })

            driver.save_screenshot(str(artifact_dir / "tongyi-video-ui-e2e-final.png"))
            result["status"] = "passed"
            return result
    except Exception:
        driver.save_screenshot(str(artifact_dir / "tongyi-video-ui-e2e-failure.png"))
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
