"""
Helpers for long-form Veo storyboard prompting and subtitle sidecar generation.

Google Veo does not expose a first-class subtitle sidecar output API in this
project's current runtime, so we treat subtitles as a synchronized companion
artifact generated from the same storyboard plan used to shape the video prompt.
"""

from __future__ import annotations

import base64
import math
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence


DEFAULT_STORYBOARD_SHOT_SECONDS = 4
SUPPORTED_STORYBOARD_SHOT_SECONDS = {4, 6, 8}
SUPPORTED_SUBTITLE_MODES = {"none", "vtt"}
PERSON_GENERATION_ALIASES = {
    "dont_allow": "DONT_ALLOW",
    "allow_adult": "ALLOW_ADULT",
    "allow_all": "ALLOW_ALL",
    "DONT_ALLOW": "DONT_ALLOW",
    "ALLOW_ADULT": "ALLOW_ADULT",
    "ALLOW_ALL": "ALLOW_ALL",
}


@dataclass(frozen=True)
class StoryboardCue:
    index: int
    start_seconds: float
    end_seconds: float
    visual_brief: str
    subtitle_text: str


def normalize_storyboard_shot_seconds(value: Optional[Any]) -> int:
    if value is None:
        return DEFAULT_STORYBOARD_SHOT_SECONDS
    try:
        candidate = int(str(value).strip())
    except (TypeError, ValueError):
        return DEFAULT_STORYBOARD_SHOT_SECONDS
    if candidate in SUPPORTED_STORYBOARD_SHOT_SECONDS:
        return candidate
    return DEFAULT_STORYBOARD_SHOT_SECONDS


def normalize_subtitle_mode(value: Optional[Any]) -> str:
    candidate = str(value or "none").strip().lower()
    if candidate in {"vtt", "srt", "both"}:
        return "vtt"
    if candidate not in SUPPORTED_SUBTITLE_MODES:
        return "none"
    return candidate


def normalize_subtitle_language(value: Optional[Any]) -> str:
    candidate = str(value or "").strip()
    return candidate or "zh-CN"


def normalize_person_generation(value: Optional[Any]) -> Optional[str]:
    if value is None:
        return None
    candidate = str(value).strip()
    if not candidate:
        return None
    return PERSON_GENERATION_ALIASES.get(candidate, PERSON_GENERATION_ALIASES.get(candidate.lower()))


def normalize_generate_audio(value: Optional[Any]) -> Optional[bool]:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    candidate = str(value).strip().lower()
    if candidate in {"1", "true", "yes", "on"}:
        return True
    if candidate in {"0", "false", "no", "off"}:
        return False
    return None


def estimate_storyboard_total_duration(
    *,
    base_duration_seconds: int,
    extension_count: int,
    extension_added_seconds: int,
) -> int:
    safe_base = max(1, int(base_duration_seconds))
    safe_extensions = max(0, int(extension_count))
    safe_added = max(0, int(extension_added_seconds))
    return safe_base + safe_extensions * safe_added


def build_storyboard_prompt(
    *,
    prompt: str,
    total_duration_seconds: int,
    shot_duration_seconds: int,
    storyboard_prompt: Optional[str] = None,
    generate_audio: Optional[bool] = None,
    subtitle_script: Optional[str] = None,
    tracked_feature: Optional[str] = None,
    tracking_overlay_text: Optional[str] = None,
) -> str:
    base_prompt = str(prompt or "").strip()
    if not base_prompt:
        return base_prompt

    explicit_storyboard_prompt = str(storyboard_prompt or "").strip()
    effective_tracked_feature = tracked_feature
    effective_tracking_overlay_text = tracking_overlay_text
    if explicit_storyboard_prompt:
        effective_tracked_feature = None
        effective_tracking_overlay_text = None
    cues = build_storyboard_cues(
        prompt=base_prompt,
        total_duration_seconds=total_duration_seconds,
        shot_duration_seconds=shot_duration_seconds,
        subtitle_script=subtitle_script,
        tracked_feature=effective_tracked_feature,
        tracking_overlay_text=effective_tracking_overlay_text,
    )

    expanded_lines: List[str] = []
    if not explicit_storyboard_prompt:
        for cue in cues:
            expanded_lines.append(
                f"- Shot {cue.index + 1} ({_human_time(cue.start_seconds)}-{_human_time(cue.end_seconds)}): {cue.visual_brief}"
            )
            if cue.subtitle_text:
                expanded_lines.append(f'  Spoken / subtitle cue: "{cue.subtitle_text}"')

    overlay_instruction = ""
    tracking_feature_text = str(effective_tracked_feature or "").strip()
    tracking_overlay_text_value = str(effective_tracking_overlay_text or "").strip()
    if tracking_feature_text and tracking_overlay_text_value:
        overlay_instruction = (
            f"Use motion-tracked on-screen text '{tracking_overlay_text_value}' that follows the feature "
            f"'{tracking_feature_text}' naturally in the relevant shots, like a polished post-produced tracked title."
        )
    elif tracking_feature_text:
        overlay_instruction = (
            f"Keep a dynamic tracking emphasis on the feature '{tracking_feature_text}' in the relevant shots."
        )

    audio_instruction = ""
    if generate_audio is True:
        audio_instruction = (
            "Generate synchronized production audio and/or narration that matches the storyboard cues. "
            "Keep speech concise, clean, and commercially polished."
        )
    elif generate_audio is False and subtitle_script:
        audio_instruction = (
            "Do not rely on visible captions alone. Stage the visuals so the subtitle cues still map cleanly to the cuts."
        )

    instructions = [
        base_prompt,
        "",
        "Additional execution requirements:",
        f"- Total runtime target: about {total_duration_seconds} seconds.",
        f"- Use a cohesive storyboard with about {shot_duration_seconds}-second shots and motivated cut points.",
        "- Preserve product identity, wardrobe, lighting continuity, and spatial continuity across every cut.",
        "- Use clear lensing, camera movement, and editorial rhythm suitable for a premium product film.",
    ]
    if overlay_instruction:
        instructions.append(f"- {overlay_instruction}")
    if audio_instruction:
        instructions.append(f"- {audio_instruction}")
    if explicit_storyboard_prompt:
        instructions.extend(
            [
                "",
                "Strict storyboard prompt (treat this as the authoritative shot plan):",
                explicit_storyboard_prompt,
            ]
        )
    else:
        instructions.extend(
            [
                "",
                "Storyboard timeline:",
                *expanded_lines,
            ]
        )
    return "\n".join(instructions).strip()


def build_storyboard_cues(
    *,
    prompt: str,
    total_duration_seconds: int,
    shot_duration_seconds: int,
    subtitle_script: Optional[str] = None,
    tracked_feature: Optional[str] = None,
    tracking_overlay_text: Optional[str] = None,
) -> List[StoryboardCue]:
    total_seconds = max(1, int(total_duration_seconds))
    shot_seconds = max(1, int(shot_duration_seconds))
    cue_count = max(1, math.ceil(total_seconds / shot_seconds))
    subtitle_lines = _build_subtitle_lines(
        prompt=prompt,
        cue_count=cue_count,
        subtitle_script=subtitle_script,
        tracked_feature=tracked_feature,
        tracking_overlay_text=tracking_overlay_text,
    )

    visual_templates = [
        "hero reveal of the product in its signature environment with a confident establishing camera move",
        "macro material and design detail pass with shallow depth of field and moving highlight control",
        "hands-on interaction shot that demonstrates the product in use with tactile realism",
        "lifestyle medium shot with model performance and smooth camera tracking",
        "feature-focused close-up that isolates the key differentiator with premium lighting",
        "environmental wide shot that places the product inside a believable use scenario",
        "dynamic follow shot that keeps the product readable while the background motion adds energy",
        "hero payoff shot that reinforces quality, brand tone, and purchase intent",
    ]
    tracking_feature_text = str(tracked_feature or "").strip()
    tracking_overlay_text_value = str(tracking_overlay_text or "").strip()

    cues: List[StoryboardCue] = []
    for index in range(cue_count):
        start_seconds = index * shot_seconds
        end_seconds = min(total_seconds, (index + 1) * shot_seconds)
        template = visual_templates[index % len(visual_templates)]
        visual_brief = template
        if tracking_feature_text:
            visual_brief = (
                f"{template}; keep the camera or subject motion anchored to the feature '{tracking_feature_text}'"
            )
        if tracking_overlay_text_value:
            visual_brief = (
                f"{visual_brief}; stage a motion-tracked text moment using '{tracking_overlay_text_value}' when it feels natural"
            )
        cues.append(
            StoryboardCue(
                index=index,
                start_seconds=float(start_seconds),
                end_seconds=float(end_seconds),
                visual_brief=visual_brief,
                subtitle_text=subtitle_lines[index] if index < len(subtitle_lines) else "",
            )
        )
    return cues


def build_subtitle_artifacts(
    *,
    prompt: str,
    total_duration_seconds: int,
    shot_duration_seconds: int,
    subtitle_mode: str,
    subtitle_language: str,
    subtitle_script: Optional[str],
    tracked_feature: Optional[str],
    tracking_overlay_text: Optional[str],
    filename_stem: str,
) -> List[Dict[str, Any]]:
    normalized_mode = normalize_subtitle_mode(subtitle_mode)
    if normalized_mode == "none":
        return []

    normalized_script = str(subtitle_script or "").strip()
    if not normalized_script:
        return []

    cues = build_storyboard_cues(
        prompt=prompt,
        total_duration_seconds=total_duration_seconds,
        shot_duration_seconds=shot_duration_seconds,
        subtitle_script=normalized_script,
        tracked_feature=tracked_feature,
        tracking_overlay_text=tracking_overlay_text,
    )
    if not cues:
        return []

    artifacts: List[Dict[str, Any]] = []
    if normalized_mode == "vtt":
        vtt_content = render_vtt(cues)
        artifacts.append(
            {
                "kind": "subtitle",
                "format": "vtt",
                "mime_type": "text/vtt",
                "filename": f"{filename_stem}.vtt",
                "language": subtitle_language,
                "data_url": _build_text_data_url(vtt_content, "text/vtt"),
            }
        )
    return artifacts


def render_vtt(cues: Sequence[StoryboardCue]) -> str:
    lines = ["WEBVTT", ""]
    for cue in cues:
        lines.append(f"{_format_vtt_time(cue.start_seconds)} --> {_format_vtt_time(cue.end_seconds)}")
        lines.append(cue.subtitle_text)
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def render_srt(cues: Sequence[StoryboardCue]) -> str:
    lines: List[str] = []
    for cue in cues:
        lines.append(str(cue.index + 1))
        lines.append(f"{_format_srt_time(cue.start_seconds)} --> {_format_srt_time(cue.end_seconds)}")
        lines.append(cue.subtitle_text)
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _build_subtitle_lines(
    *,
    prompt: str,
    cue_count: int,
    subtitle_script: Optional[str],
    tracked_feature: Optional[str],
    tracking_overlay_text: Optional[str],
) -> List[str]:
    explicit_lines = _split_subtitle_script(subtitle_script)
    if explicit_lines:
        return explicit_lines[:cue_count]
    return []


def _default_subtitle_lines(
    prompt: str,
    cue_count: int,
    tracked_feature: Optional[str],
    tracking_overlay_text: Optional[str],
) -> List[str]:
    subject = _summarize_subject(prompt)
    feature = str(tracked_feature or "").strip()
    overlay = str(tracking_overlay_text or "").strip()
    generic_lines = [
        f"Meet {subject}.",
        "Premium design, clean movement, immediate presence.",
        f"Focus on {feature}." if feature else "Zoom in on the signature detail.",
        "Built for real-life use and everyday motion.",
        "See the product in authentic lifestyle moments.",
        overlay if overlay else "Performance stays clear from every angle.",
        "Texture, finish, and function stay readable in motion.",
        f"{subject}, ready for the next scene.",
    ]
    if cue_count <= len(generic_lines):
        return generic_lines[:cue_count]
    result = list(generic_lines)
    while len(result) < cue_count:
        result.append(f"{subject}, shot {len(result) + 1}.")
    return result[:cue_count]


def _split_subtitle_script(script: Optional[str]) -> List[str]:
    raw = str(script or "").strip()
    if not raw:
        return []
    pieces = re.split(r"(?:\r?\n)+|\s*\|\s*", raw)
    lines = []
    for piece in pieces:
        normalized = re.sub(r"^\s*[-*•\d.]+\s*", "", piece).strip()
        if normalized:
            lines.append(normalized)
    return lines


def _summarize_subject(prompt: str, max_words: int = 8) -> str:
    cleaned = re.sub(r"\s+", " ", str(prompt or "").strip())
    if not cleaned:
        return "the product"
    words = cleaned.split(" ")
    snippet = " ".join(words[:max_words]).strip(" ,.;:!?")
    return snippet or "the product"


def _human_time(value: float) -> str:
    if float(value).is_integer():
        return f"{int(value)}s"
    return f"{value:.1f}s"


def _format_vtt_time(seconds: float) -> str:
    total_milliseconds = max(0, int(round(seconds * 1000)))
    hours = total_milliseconds // 3_600_000
    minutes = (total_milliseconds % 3_600_000) // 60_000
    secs = (total_milliseconds % 60_000) // 1000
    milliseconds = total_milliseconds % 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{milliseconds:03d}"


def _format_srt_time(seconds: float) -> str:
    total_milliseconds = max(0, int(round(seconds * 1000)))
    hours = total_milliseconds // 3_600_000
    minutes = (total_milliseconds % 3_600_000) // 60_000
    secs = (total_milliseconds % 60_000) // 1000
    milliseconds = total_milliseconds % 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{milliseconds:03d}"


def _build_text_data_url(text: str, mime_type: str) -> str:
    encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
    return f"data:{mime_type};charset=utf-8;base64,{encoded}"
