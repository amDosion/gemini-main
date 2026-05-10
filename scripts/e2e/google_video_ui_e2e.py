#!/usr/bin/env python3
"""Run a real browser E2E test for Google Video mode.

This test drives the local frontend, uses the currently active real user session
from the backend database, selects a prompt enhancement model in the UI, starts a
real Veo generation, and verifies that the generated video loads in the browser.

It intentionally performs a real paid/provider call. Run it only when that is
desired:

    backend/.venv/bin/python scripts/e2e/google_video_ui_e2e.py
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from selenium import webdriver  # noqa: E402
from selenium.common.exceptions import TimeoutException, WebDriverException  # noqa: E402
from selenium.webdriver.common.by import By  # noqa: E402
from selenium.webdriver.firefox.options import Options  # noqa: E402
from selenium.webdriver.support import expected_conditions as EC  # noqa: E402
from selenium.webdriver.support.ui import Select, WebDriverWait  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.models.db_models import ConfigProfile, MessageAttachment, MessageIndex, MessagesVideoGen, User, UserSettings  # noqa: E402
from app.services.gemini.base.video_storyboard import strip_audio_prompt_cues  # noqa: E402
from app.services.storage.local_provider import resolve_local_public_file_path  # noqa: E402


DEFAULT_PROMPT = (
    "UI e2e test: a small red cube rotating slowly on a clean white tabletop, "
    "static camera, soft studio light, four seconds."
)


def _find_active_google_user(user_id: str | None) -> tuple[str, str]:
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.status == "active").all()
        if user_id:
            users = [user for user in users if str(user.id) == user_id]

        for user in users:
            uid = str(user.id)
            if not user.access_token:
                continue
            settings = db.query(UserSettings).filter(UserSettings.user_id == uid).first()
            active_profile_id = str(getattr(settings, "active_profile_id", "") or "")
            profile = None
            if active_profile_id:
                profile = (
                    db.query(ConfigProfile)
                    .filter(ConfigProfile.user_id == uid, ConfigProfile.id == active_profile_id)
                    .first()
                )
            if profile is None:
                profile = (
                    db.query(ConfigProfile)
                    .filter(ConfigProfile.user_id == uid, ConfigProfile.provider_id.like("google%"))
                    .order_by(ConfigProfile.updated_at.desc())
                    .first()
                )
            if profile and str(profile.provider_id or "").lower().startswith("google") and profile.api_key:
                return uid, str(user.access_token)
    finally:
        db.close()
    raise RuntimeError("No active user with a saved access_token and Google profile was found.")


def _same_origin_cookie_domain(base_url: str) -> str:
    parsed = urlparse(base_url)
    return parsed.hostname or "127.0.0.1"


def _inject_auth(driver: webdriver.Firefox, base_url: str, token: str) -> None:
    driver.get(base_url)
    driver.execute_script(
        "localStorage.setItem('access_token', arguments[0]);"
        "localStorage.setItem('has_active_profile','true');",
        token,
    )
    cookie = {"name": "access_token", "value": token, "path": "/"}
    domain = _same_origin_cookie_domain(base_url)
    if domain not in {"localhost", "127.0.0.1"}:
        cookie["domain"] = domain
    driver.add_cookie(cookie)


def _click_if_present(driver: webdriver.Firefox, xpath: str) -> None:
    try:
        driver.find_element(By.XPATH, xpath).click()
    except Exception:
        return


def _set_control_text(driver: webdriver.Firefox, element, value: str) -> None:
    driver.execute_script(
        """
        const element = arguments[0];
        const value = arguments[1];
        const setter = Object.getOwnPropertyDescriptor(element.__proto__, 'value')?.set;
        if (setter) {
          setter.call(element, value);
        } else {
          element.value = value;
        }
        element.dispatchEvent(new Event('input', { bubbles: true }));
        element.dispatchEvent(new Event('change', { bubbles: true }));
        """,
        element,
        value,
    )


def _ensure_video_mode(driver: webdriver.Firefox, wait: WebDriverWait) -> None:
    wait.until(EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='Video']"))).click()
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "textarea[placeholder*='描述你想生成的视频']")))


def _ensure_enhance_model_select(driver: webdriver.Firefox, wait: WebDriverWait):
    selector = "select[aria-label='增强提示词模型']"
    try:
        return wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
    except TimeoutException:
        _click_if_present(driver, "//button[contains(normalize-space(), '高级参数')]")
        return wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))


def _resolution_button_text(resolution: str) -> str:
    normalized = str(resolution or "").strip().lower()
    if normalized == "4k":
        return "4K UHD"
    if normalized == "1080p":
        return "1080p Full HD"
    return "720p HD"


def _aspect_ratio_button_text(aspect_ratio: str) -> str:
    normalized = str(aspect_ratio or "").strip()
    if normalized == "9:16":
        return "9:16 Portrait"
    return "16:9 Landscape"


def _button_is_selected(button) -> bool:
    class_name = button.get_attribute("class") or ""
    return "text-white" in class_name or "bg-emerald" in class_name or button.get_attribute("aria-pressed") == "true"


def _select_resolution(driver: webdriver.Firefox, wait: WebDriverWait, resolution: str) -> str:
    label = _resolution_button_text(resolution)
    xpath = f"//button[contains(normalize-space(), '{label}')]"
    button = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
    button.click()

    def selected(drv: webdriver.Firefox) -> bool:
        candidate = drv.find_element(By.XPATH, xpath)
        return _button_is_selected(candidate)

    wait.until(selected)
    return " ".join((driver.find_element(By.XPATH, xpath).text or "").split())


def _select_aspect_ratio(driver: webdriver.Firefox, wait: WebDriverWait, aspect_ratio: str) -> str:
    label = _aspect_ratio_button_text(aspect_ratio)
    xpath = f"//button[contains(normalize-space(), '{label}')]"
    button = wait.until(EC.element_to_be_clickable((By.XPATH, xpath)))
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", button)
    button.click()

    def selected(drv: webdriver.Firefox) -> bool:
        candidate = drv.find_element(By.XPATH, xpath)
        return _button_is_selected(candidate)

    wait.until(selected)
    return " ".join((driver.find_element(By.XPATH, xpath).text or "").split())


def _select_value(driver: webdriver.Firefox, wait: WebDriverWait, selector: str, value: str) -> bool:
    try:
        element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
        Select(element).select_by_value(value)
        wait.until(lambda drv: drv.find_element(By.CSS_SELECTOR, selector).get_attribute("value") == value)
        return True
    except Exception:
        return False


def _split_storyboard_prompt(prompt: str) -> tuple[str, list[str]]:
    text = str(prompt or "").strip()
    if not text:
        return "", []
    matches = list(re.finditer(r"(?<!\d)\d+\s*-\s*\d+s?\s*:", text))
    if len(matches) <= 1:
        return text, []

    chunks: list[str] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        chunks.append(text[match.start():end].strip())
    return chunks[0], chunks[1:]


def _fit_extension_storyboard_prompts(prompts: list[str], extension_count: int) -> list[str]:
    if extension_count <= 0:
        return []
    selected = prompts[:extension_count]
    if len(prompts) > extension_count and selected:
        selected[-1] = "\n".join(prompts[extension_count - 1 :]).strip()
    return selected


def _current_video_sources(driver: webdriver.Firefox) -> set[str]:
    sources: set[str] = set()
    for video in driver.find_elements(By.TAG_NAME, "video"):
        src = video.get_attribute("src") or ""
        if src:
            sources.add(src)
        for source in video.find_elements(By.TAG_NAME, "source"):
            source_src = source.get_attribute("src") or ""
            if source_src:
                sources.add(source_src)
    return sources


def _verify_video_metadata(driver: webdriver.Firefox, video_url: str, timeout_seconds: int) -> dict[str, Any]:
    driver.set_script_timeout(timeout_seconds + 10)
    return driver.execute_async_script(
        """
        const url = arguments[0];
        const timeoutMs = arguments[1] * 1000;
        const done = arguments[arguments.length - 1];
        const video = document.createElement('video');
        video.muted = true;
        video.preload = 'metadata';
        video.src = url;
        const timer = setTimeout(() => done({
          status: 'timeout',
          readyState: video.readyState,
          error: video.error && video.error.code,
          src: video.currentSrc || video.src
        }), timeoutMs);
        video.onloadedmetadata = () => {
          clearTimeout(timer);
          done({
            status: 'loadedmetadata',
            duration: video.duration,
            readyState: video.readyState,
            videoWidth: video.videoWidth,
            videoHeight: video.videoHeight,
            src: video.currentSrc || video.src
          });
        };
        video.onerror = () => {
          clearTimeout(timer);
          done({
            status: 'error',
            readyState: video.readyState,
            error: video.error && video.error.code,
            src: video.currentSrc || video.src
          });
        };
        document.body.appendChild(video);
        video.load();
        """,
        video_url,
        timeout_seconds,
    )


def _verify_video_metadata_with_retries(
    driver: webdriver.Firefox,
    video_url: str,
    timeout_seconds: int,
    *,
    attempts: int = 3,
    retry_delay_seconds: int = 3,
) -> dict[str, Any]:
    last_result: dict[str, Any] = {}
    for attempt in range(1, max(1, attempts) + 1):
        last_result = _verify_video_metadata(driver, video_url, timeout_seconds)
        last_result["attempt"] = attempt
        if last_result.get("status") == "loadedmetadata":
            return last_result
        if attempt < attempts:
            time.sleep(retry_delay_seconds)
    return last_result


def _inspect_rendered_video_metadata(driver: webdriver.Firefox, video_url: str) -> dict[str, Any]:
    return driver.execute_script(
        """
        const url = arguments[0];
        const matches = [...document.querySelectorAll('video')]
          .filter((video) => [video.currentSrc, video.src].some((src) => src === url))
          .map((video) => ({
            src: video.currentSrc || video.src,
            duration: Number.isFinite(video.duration) ? video.duration : null,
            readyState: video.readyState,
            networkState: video.networkState,
            error: video.error && video.error.code,
            videoWidth: video.videoWidth,
            videoHeight: video.videoHeight,
          }));
        const loaded = matches.find((video) =>
          video.readyState >= 1
          && Number.isFinite(video.duration)
          && video.duration > 0
          && video.videoWidth > 0
          && video.videoHeight > 0
        );
        if (loaded) {
          return {
            status: 'loadedmetadata',
            verification_source: 'rendered_dom_video',
            duration: loaded.duration,
            readyState: loaded.readyState,
            networkState: loaded.networkState,
            error: loaded.error,
            videoWidth: loaded.videoWidth,
            videoHeight: loaded.videoHeight,
            src: loaded.src,
            renderedVideoCount: matches.length,
          };
        }
        return {
          status: 'not_loaded',
          verification_source: 'rendered_dom_video',
          renderedVideoCount: matches.length,
          matches,
        };
        """,
        video_url,
    )


def _public_path_from_url(video_url: str) -> str:
    parsed = urlparse(video_url)
    return parsed.path if parsed.scheme else video_url


def _collect_landing_info(video_url: str) -> dict[str, Any]:
    public_path = _public_path_from_url(video_url)
    local_path = resolve_local_public_file_path(public_path)
    landing: dict[str, Any] = {
        "public_path": public_path,
        "local_path": str(local_path) if local_path else None,
        "local_exists": bool(local_path and local_path.exists()),
        "local_size": local_path.stat().st_size if local_path and local_path.exists() else None,
        "attachment_records": [],
        "message_persistence_ok": False,
    }

    db = SessionLocal()
    try:
        records = (
            db.query(MessageAttachment)
            .filter(MessageAttachment.url == public_path)
            .order_by(MessageAttachment.message_id.desc())
            .limit(5)
            .all()
        )
        attachment_records: list[dict[str, Any]] = []
        for record in records:
            index_row = db.query(MessageIndex).filter(MessageIndex.id == record.message_id).first()
            video_row = db.query(MessagesVideoGen).filter(MessagesVideoGen.id == record.message_id).first()
            attachment_records.append({
                "id": record.id,
                "message_id": record.message_id,
                "session_id": record.session_id,
                "mime_type": record.mime_type,
                "name": record.name,
                "upload_status": record.upload_status,
                "size": record.size,
                "message_index_present": index_row is not None,
                "video_message_present": video_row is not None,
            })
        landing["attachment_records"] = attachment_records
        landing["message_persistence_ok"] = any(
            record.get("message_index_present") and record.get("video_message_present")
            for record in attachment_records
        )
    finally:
        db.close()
    return landing


def _sanitize_video_prompt_text(text: str, *, generate_audio: str, keep_audio_cues: bool) -> str:
    if keep_audio_cues or str(generate_audio).lower() == "true":
        return str(text or "")
    return strip_audio_prompt_cues(text)


def run(args: argparse.Namespace) -> dict[str, Any]:
    user_id, token = _find_active_google_user(args.user_id)
    artifact_dir = Path(args.artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    prompt_text = _sanitize_video_prompt_text(
        args.prompt,
        generate_audio=args.generate_audio,
        keep_audio_cues=args.keep_audio_cues,
    )
    storyboard_prompt_text = _sanitize_video_prompt_text(
        args.storyboard_prompt,
        generate_audio=args.generate_audio,
        keep_audio_cues=args.keep_audio_cues,
    )

    options = Options()
    if args.headless:
        options.add_argument("-headless")
    options.set_preference("media.volume_scale", "0.0")
    options.set_preference("dom.webnotifications.enabled", False)

    driver = webdriver.Firefox(options=options)
    result: dict[str, Any] = {
        "status": "started",
        "base_url": args.base_url,
        "user_id": user_id,
        "prompt": prompt_text,
        "raw_prompt": args.prompt,
        "enhance_model": args.enhance_model,
        "image_path": str(Path(args.image_path).resolve()) if args.image_path else None,
        "storyboard_prompt": storyboard_prompt_text,
        "raw_storyboard_prompt": args.storyboard_prompt,
        "video_extension_count": args.video_extension_count,
        "duration_seconds": args.duration_seconds,
        "aspect_ratio": args.aspect_ratio,
        "resolution": args.resolution,
        "generate_audio": args.generate_audio,
        "keep_audio_cues": args.keep_audio_cues,
        "video_url": None,
        "metadata": None,
    }
    try:
        driver.set_window_size(args.width, args.height)
        wait = WebDriverWait(driver, args.ui_timeout_seconds)
        _inject_auth(driver, args.base_url, token)
        driver.get(args.base_url)
        _ensure_video_mode(driver, wait)

        result["selected_aspect_ratio_label"] = _select_aspect_ratio(driver, wait, args.aspect_ratio)
        result["selected_resolution_label"] = _select_resolution(driver, wait, args.resolution)
        _click_if_present(driver, f"//button[normalize-space()='{args.duration_seconds}s']")
        selected_extension_values: dict[str, str] = {}
        for selector in ("select[aria-label='延长次数']", "select[aria-label='延长后总时长']"):
            if _select_value(driver, wait, selector, str(args.video_extension_count)):
                selected_extension_values[selector] = driver.find_element(By.CSS_SELECTOR, selector).get_attribute("value")
        result["selected_extension_values"] = selected_extension_values
        result["selected_generate_audio"] = None
        if _select_value(driver, wait, "select[aria-label='生成音频']", str(args.generate_audio).lower()):
            result["selected_generate_audio"] = driver.find_element(
                By.CSS_SELECTOR,
                "select[aria-label='生成音频']",
            ).get_attribute("value")

        enhance_select = _ensure_enhance_model_select(driver, wait)
        Select(enhance_select).select_by_value(args.enhance_model)
        result["selected_enhance_model"] = enhance_select.get_attribute("value")

        if storyboard_prompt_text:
            base_storyboard_prompt, extension_storyboard_prompts = _split_storyboard_prompt(storyboard_prompt_text)
            storyboard_area = driver.find_element(By.CSS_SELECTOR, "textarea[aria-label='分镜提示词']")
            _set_control_text(driver, storyboard_area, base_storyboard_prompt or storyboard_prompt_text)
            result["selected_storyboard_prompt"] = base_storyboard_prompt or storyboard_prompt_text
            selected_extension_storyboards: list[str] = []
            fitted_extension_prompts = _fit_extension_storyboard_prompts(
                extension_storyboard_prompts,
                max(0, args.video_extension_count),
            )
            for index, extension_prompt in enumerate(fitted_extension_prompts):
                try:
                    segment_area = driver.find_element(By.CSS_SELECTOR, f"textarea[aria-label='延长 {index + 1} 分镜提示词']")
                except Exception:
                    continue
                _set_control_text(driver, segment_area, extension_prompt)
                selected_extension_storyboards.append(extension_prompt)
            result["selected_storyboard_segments"] = selected_extension_storyboards

        if args.image_path:
            image_path = Path(args.image_path).resolve()
            if not image_path.exists():
                raise FileNotFoundError(str(image_path))
            file_input = driver.find_element(By.CSS_SELECTOR, "input[type='file']")
            file_input.send_keys(str(image_path))
            time.sleep(1)

        prompt_area = driver.find_element(By.CSS_SELECTOR, "textarea[placeholder*='描述你想生成的视频']")
        _set_control_text(driver, prompt_area, prompt_text)

        if args.dry_run_controls:
            result["status"] = "controls_selected"
            driver.save_screenshot(str(artifact_dir / "google-video-ui-e2e-controls.png"))
            return result

        existing_sources = _current_video_sources(driver)
        result["clicked_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
        wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(normalize-space(), '生成视频')]"))).click()

        deadline = time.time() + args.generation_timeout_seconds
        saw_loading = False
        last_text = ""
        while time.time() < deadline:
            time.sleep(args.poll_seconds)
            body_text = driver.find_element(By.TAG_NAME, "body").text
            last_text = body_text[-3000:]
            if "生成中" in body_text or "Generating" in body_text or "正在" in body_text:
                saw_loading = True

            for source in _current_video_sources(driver):
                if source and source not in existing_sources:
                    metadata = _verify_video_metadata_with_retries(driver, source, args.metadata_timeout_seconds)
                    if metadata.get("status") != "loadedmetadata":
                        rendered_metadata = _inspect_rendered_video_metadata(driver, source)
                        if rendered_metadata.get("status") == "loadedmetadata":
                            rendered_metadata["hidden_video_probe"] = metadata
                            metadata = rendered_metadata
                    landing = _collect_landing_info(source)
                    result.update(
                        {
                            "status": "video_rendered",
                            "video_url": source,
                            "metadata": metadata,
                            "landing": landing,
                            "saw_loading": saw_loading,
                            "body_tail": last_text,
                        }
                    )
                    driver.save_screenshot(str(artifact_dir / "google-video-ui-e2e-success.png"))
                    if metadata.get("status") != "loadedmetadata":
                        result["status"] = "video_rendered_but_metadata_failed"
                    elif args.require_db_message and not landing.get("message_persistence_ok"):
                        result["status"] = "video_rendered_but_db_message_missing"
                    return result

            lowered = body_text.lower()
            if any(marker in body_text for marker in ("生成失败", "处理失败", "服务方法调用失败", "错误")) or "failed" in lowered:
                result.update(
                    {
                        "status": "ui_error",
                        "saw_loading": saw_loading,
                        "body_tail": last_text,
                    }
                )
                driver.save_screenshot(str(artifact_dir / "google-video-ui-e2e-error.png"))
                return result

        result.update(
            {
                "status": "timeout_waiting_for_video",
                "saw_loading": saw_loading,
                "body_tail": last_text,
            }
        )
        driver.save_screenshot(str(artifact_dir / "google-video-ui-e2e-timeout.png"))
        return result
    finally:
        try:
            driver.quit()
        except WebDriverException:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Run real Google Video UI E2E generation.")
    parser.add_argument("--base-url", default="http://127.0.0.1:21573")
    parser.add_argument("--user-id", default=None)
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--enhance-model", default="gemini-3.1-flash-lite-preview")
    parser.add_argument("--image-path", default=None)
    parser.add_argument("--storyboard-prompt", default="")
    parser.add_argument("--video-extension-count", default=0, type=int)
    parser.add_argument("--duration-seconds", default=4, type=int)
    parser.add_argument("--aspect-ratio", default="16:9", choices=["16:9", "9:16"])
    parser.add_argument("--resolution", default="720p", choices=["720p", "1080p", "4k"])
    parser.add_argument("--generate-audio", default="false", choices=["false", "true"])
    parser.add_argument("--keep-audio-cues", action="store_true")
    parser.add_argument("--skip-db-message-check", action="store_true")
    parser.add_argument("--generation-timeout-seconds", default=40 * 60, type=int)
    parser.add_argument("--metadata-timeout-seconds", default=30, type=int)
    parser.add_argument("--ui-timeout-seconds", default=45, type=int)
    parser.add_argument("--poll-seconds", default=5, type=int)
    parser.add_argument("--artifact-dir", default="/tmp/gemini-main-ui-e2e")
    parser.add_argument("--width", default=1440, type=int)
    parser.add_argument("--height", default=1000, type=int)
    parser.add_argument("--headful", action="store_true")
    parser.add_argument("--dry-run-controls", action="store_true")
    args = parser.parse_args()
    args.headless = not args.headful
    args.require_db_message = not args.skip_db_message_check

    result = run(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.dry_run_controls:
        return 0 if result.get("status") == "controls_selected" else 1
    return 0 if result.get("status") == "video_rendered" and result.get("metadata", {}).get("status") == "loadedmetadata" else 1


if __name__ == "__main__":
    raise SystemExit(main())
