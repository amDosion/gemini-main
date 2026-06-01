"""Shared helpers for video prompt enhancement.

Video extension requests have two prompt layers:
- the main prompt, which defines global identity/style/constraints
- optional storyboard segment prompts, which define per-extension changes

When a user enables prompt enhancement, both layers should be rewritten by the
same selected text model so continuation segments do not remain raw while the
base prompt is enhanced.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional

from .video_extension_chain import normalize_storyboard_segments


PromptEnhancer = Callable[[str], Awaitable[Optional[str]]]


@dataclass(frozen=True)
class VideoPromptEnhancementBundle:
    effective_prompt: str
    enhanced_prompt: Optional[str]
    request_kwargs: Dict[str, Any]
    original_storyboard_segments: List[str]
    enhanced_storyboard_segments: List[str]

    @property
    def storyboard_was_enhanced(self) -> bool:
        return bool(self.original_storyboard_segments) and (
            self.enhanced_storyboard_segments != self.original_storyboard_segments
        )


async def enhance_video_prompt_bundle(
    *,
    prompt: str,
    request_kwargs: Dict[str, Any],
    extension_count: int,
    enhance_requested: bool,
    enhance_prompt: PromptEnhancer,
) -> VideoPromptEnhancementBundle:
    next_kwargs = dict(request_kwargs)
    original_prompt = str(prompt or "").strip()
    original_storyboard_segments = normalize_storyboard_segments(request_kwargs)

    if not enhance_requested:
        return VideoPromptEnhancementBundle(
            effective_prompt=prompt,
            enhanced_prompt=None,
            request_kwargs=next_kwargs,
            original_storyboard_segments=original_storyboard_segments,
            enhanced_storyboard_segments=original_storyboard_segments,
        )

    enhanced_main = await _enhance_one(original_prompt, enhance_prompt)
    effective_prompt = enhanced_main or prompt
    enhanced_storyboard_segments = list(original_storyboard_segments)

    if extension_count > 0 and original_storyboard_segments:
        rewritten_segments: List[str] = []
        for segment in original_storyboard_segments:
            stripped = str(segment or "").strip()
            if not stripped:
                rewritten_segments.append(segment)
                continue
            rewritten_segments.append(await _enhance_one(stripped, enhance_prompt) or segment)
        enhanced_storyboard_segments = rewritten_segments
        next_kwargs["storyboard_segments"] = rewritten_segments
        next_kwargs.pop("storyboardSegments", None)

    return VideoPromptEnhancementBundle(
        effective_prompt=effective_prompt,
        enhanced_prompt=enhanced_main,
        request_kwargs=next_kwargs,
        original_storyboard_segments=original_storyboard_segments,
        enhanced_storyboard_segments=enhanced_storyboard_segments,
    )


def apply_video_prompt_enhancement_metadata(
    result: Dict[str, Any],
    bundle: VideoPromptEnhancementBundle,
) -> Dict[str, Any]:
    if bundle.enhanced_prompt:
        result["enhanced_prompt"] = bundle.enhanced_prompt
        result["prompt_enhancement_strategy"] = "local_llm"
    if bundle.storyboard_was_enhanced:
        result["original_storyboard_segments"] = bundle.original_storyboard_segments
        result["enhanced_storyboard_segments"] = bundle.enhanced_storyboard_segments
        result["storyboard_prompt_enhancement_strategy"] = "local_llm"
    return result


async def _enhance_one(prompt: str, enhance_prompt: PromptEnhancer) -> Optional[str]:
    original = str(prompt or "").strip()
    if not original:
        return None
    enhanced = await enhance_prompt(original)
    rewritten = str(enhanced or "").strip()
    if rewritten and rewritten != original:
        return rewritten
    return None
