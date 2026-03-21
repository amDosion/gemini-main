"""
Image Edit Workflow - 图像编辑工作流

统一走 WorkflowEngine：
- start -> input_image -> tool(image_edit family) -> end
- 与编辑器主执行链保持同一内核和结果字段
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy.orm import Session

from ....agent.agent_llm_service import AgentLLMService
from ....agent.workflow_engine import WorkflowEngine

logger = logging.getLogger(__name__)


class ImageEditWorkflow:
    """图像编辑工作流（WorkflowEngine 单内核实现）"""

    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = str(user_id or "").strip()
        logger.info("[ImageEditWorkflow] Initialized with WorkflowEngine")

    @staticmethod
    def _normalize_edit_mode(edit_mode: Optional[str]) -> str:
        raw = str(edit_mode or "").strip().lower().replace("_", "-")
        if not raw:
            return "image-chat-edit"

        aliases = {
            "chat": "image-chat-edit",
            "default": "image-chat-edit",
            "image-chat-edit": "image-chat-edit",
            "mask": "image-mask-edit",
            "image-mask-edit": "image-mask-edit",
            "inpaint": "image-inpainting",
            "inpainting": "image-inpainting",
            "image-inpainting": "image-inpainting",
            "background": "image-background-edit",
            "background-edit": "image-background-edit",
            "image-background-edit": "image-background-edit",
            "recontext": "image-recontext",
            "image-recontext": "image-recontext",
            "outpaint": "image-outpainting",
            "outpainting": "image-outpainting",
            "image-outpainting": "image-outpainting",
            "expand": "image-outpainting",
        }
        return aliases.get(raw, "image-chat-edit")

    @classmethod
    def _resolve_tool_name(cls, edit_mode: str) -> str:
        normalized_mode = cls._normalize_edit_mode(edit_mode)
        mapping = {
            "image-chat-edit": "image_chat_edit",
            "image-mask-edit": "image_mask_edit",
            "image-inpainting": "image_inpainting",
            "image-background-edit": "image_background_edit",
            "image-recontext": "image_recontext",
            "image-outpainting": "image_outpainting",
        }
        return mapping.get(normalized_mode, "image_chat_edit")

    @classmethod
    def _build_graph(cls, edit_mode: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        tool_name = cls._resolve_tool_name(edit_mode)
        nodes = [
            {
                "id": "start",
                "type": "start",
                "data": {"type": "start"},
            },
            {
                "id": "input-image",
                "type": "input_image",
                "data": {"type": "input_image"},
            },
            {
                "id": "image-edit",
                "type": "tool",
                "data": {
                    "type": "tool",
                    "tool_name": tool_name,
                    "tool_args_template": {
                        "imageUrl": "{{input.imageUrl}}",
                        "editPrompt": "{{input.task}}",
                        "editMode": "{{input.edit_mode}}",
                        "preserveProductIdentity": True,
                    },
                },
            },
            {
                "id": "end",
                "type": "end",
                "data": {"type": "end"},
            },
        ]
        edges = [
            {"id": "edge-start-input", "source": "start", "target": "input-image"},
            {"id": "edge-input-tool", "source": "input-image", "target": "image-edit"},
            {"id": "edge-tool-end", "source": "image-edit", "target": "end"},
        ]
        return nodes, edges

    @staticmethod
    def _collect_steps(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        steps: List[Dict[str, Any]] = []
        for event in events:
            if not isinstance(event, dict):
                continue
            event_type = str(event.get("event_type") or "").strip()
            node_id = str(event.get("nodeId") or event.get("node_id") or "").strip()
            if not event_type or not node_id:
                continue

            if event_type == "node_complete":
                steps.append(
                    {
                        "node_id": node_id,
                        "status": "completed",
                        "timestamp": event.get("timestamp"),
                    }
                )
            elif event_type == "node_error":
                steps.append(
                    {
                        "node_id": node_id,
                        "status": "failed",
                        "timestamp": event.get("timestamp"),
                        "error": event.get("error"),
                    }
                )
            elif event_type == "node_skipped":
                steps.append(
                    {
                        "node_id": node_id,
                        "status": "skipped",
                        "timestamp": event.get("timestamp"),
                        "reason": event.get("reason"),
                    }
                )
        return steps

    @staticmethod
    def _extract_tool_result(outputs: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(outputs, dict):
            return {}
        tool_node_output = outputs.get("image-edit") or outputs.get("image_edit")
        if not isinstance(tool_node_output, dict):
            return {}
        result = tool_node_output.get("result")
        if isinstance(result, dict):
            return result
        return tool_node_output if isinstance(tool_node_output, dict) else {}

    @staticmethod
    def _normalize_artifact(tool_result: Dict[str, Any]) -> Dict[str, Any]:
        images = tool_result.get("images") if isinstance(tool_result.get("images"), list) else []
        image_urls = tool_result.get("imageUrls") if isinstance(tool_result.get("imageUrls"), list) else []
        if not image_urls:
            image_urls = [str(item.get("url") or "").strip() for item in images if isinstance(item, dict)]
            image_urls = [url for url in image_urls if url]

        return {
            "images": images,
            "image_urls": image_urls,
            "primary_image_url": image_urls[0] if image_urls else str(tool_result.get("imageUrl") or "").strip() or None,
            "count": int(tool_result.get("count") or len(image_urls) or len(images) or 0),
        }

    @staticmethod
    def _normalize_quality(tool_result: Dict[str, Any]) -> Dict[str, Any]:
        validation = tool_result.get("validation") if isinstance(tool_result.get("validation"), dict) else {}
        passed = validation.get("passed")
        return {
            "validation": validation,
            "passed": bool(passed) if passed is not None else None,
            "issues": validation.get("issues") if isinstance(validation.get("issues"), list) else [],
        }

    @staticmethod
    def _normalize_trace(
        *,
        tool_result: Dict[str, Any],
        node_states: Dict[str, Any],
        steps: List[Dict[str, Any]],
        errors: Dict[str, Any],
    ) -> Dict[str, Any]:
        runtime_hints: List[str] = []
        provider = str(tool_result.get("provider") or "").strip()
        model = str(tool_result.get("model") or "").strip()
        tool_name = str(tool_result.get("tool") or "image_edit").strip() or "image_edit"

        if provider:
            runtime_hints.append(provider)
        if model:
            runtime_hints.append(model)

        return {
            "tool": tool_name,
            "provider": provider or None,
            "model": model or None,
            "attempt": int(tool_result.get("attempt") or 0) or None,
            "max_attempts": int(tool_result.get("maxAttempts") or 0) or None,
            "mode": str(tool_result.get("mode") or "").strip() or None,
            "runtime_hints": runtime_hints,
            "node_states": node_states,
            "steps": steps,
            "errors": errors,
        }

    async def execute(
        self,
        image_url: str,
        edit_prompt: str,
        edit_mode: Optional[str] = None,
    ) -> Dict[str, Any]:
        """执行图像编辑工作流。"""
        normalized_image_url = str(image_url or "").strip()
        normalized_edit_prompt = str(edit_prompt or "").strip()
        normalized_edit_mode = self._normalize_edit_mode(edit_mode)

        if not normalized_image_url:
            return {"success": False, "error": "image_url is required"}
        if not normalized_edit_prompt:
            return {"success": False, "error": "edit_prompt is required"}

        logger.info(
            "[ImageEditWorkflow] Starting execution: mode=%s prompt=%s",
            normalized_edit_mode,
            normalized_edit_prompt[:80],
        )

        try:
            llm_service = AgentLLMService(user_id=self.user_id, db=self.db)
            engine = WorkflowEngine(db=self.db, llm_service=llm_service)
            nodes, edges = self._build_graph(normalized_edit_mode)

            events: List[Dict[str, Any]] = []

            async def on_event(event_type: str, data: Dict[str, Any]) -> None:
                payload = {"event_type": event_type}
                if isinstance(data, dict):
                    payload.update(data)
                events.append(payload)

            result = await engine.execute(
                nodes=nodes,
                edges=edges,
                initial_input={
                    "task": normalized_edit_prompt,
                    "text": normalized_edit_prompt,
                    "imageUrl": normalized_image_url,
                    "imageUrls": [normalized_image_url],
                    "edit_mode": normalized_edit_mode,
                },
                on_event=on_event,
            )

            outputs = result.get("outputs") if isinstance(result, dict) else {}
            if not isinstance(outputs, dict):
                outputs = {}

            tool_result = self._extract_tool_result(outputs)
            steps = self._collect_steps(events)
            errors = result.get("errors") if isinstance(result, dict) and isinstance(result.get("errors"), dict) else {}
            node_states = result.get("node_states") if isinstance(result, dict) and isinstance(result.get("node_states"), dict) else {}

            artifact = self._normalize_artifact(tool_result)
            quality = self._normalize_quality(tool_result)
            trace = self._normalize_trace(
                tool_result=tool_result,
                node_states=node_states,
                steps=steps,
                errors=errors,
            )
            success = bool(artifact.get("primary_image_url")) and not bool(errors)

            return {
                "success": success,
                "workflow": "image_edit",
                "input": {
                    "image_url": normalized_image_url,
                    "edit_prompt": normalized_edit_prompt,
                    "edit_mode": normalized_edit_mode,
                },
                "artifact": artifact,
                "quality": quality,
                "trace": trace,
                "analysis_result": None,
                "edit_advice": None,
                "edited_image": tool_result,
                "quality_report": quality,
                "final_output": result.get("final_output") if isinstance(result, dict) else None,
                "steps": steps,
                "node_states": node_states,
                "errors": errors,
                # Legacy compatibility fields.
                "image_url": normalized_image_url,
                "edit_prompt": normalized_edit_prompt,
                "edit_mode": normalized_edit_mode,
                "imageUrl": artifact.get("primary_image_url"),
                "imageUrls": artifact.get("image_urls") or [],
            }
        except Exception as exc:
            logger.error("[ImageEditWorkflow] Execution failed: %s", exc, exc_info=True)
            return {
                "success": False,
                "workflow": "image_edit",
                "input": {
                    "image_url": normalized_image_url,
                    "edit_prompt": normalized_edit_prompt,
                    "edit_mode": normalized_edit_mode,
                },
                "artifact": {
                    "images": [],
                    "image_urls": [],
                    "primary_image_url": None,
                    "count": 0,
                },
                "quality": {
                    "validation": {},
                    "passed": None,
                    "issues": [],
                },
                "trace": {
                    "tool": "image_edit",
                    "provider": None,
                    "model": None,
                    "attempt": None,
                    "max_attempts": None,
                    "mode": normalized_edit_mode,
                    "runtime_hints": [],
                    "node_states": {},
                    "steps": [],
                    "errors": {},
                },
                "error": str(exc),
                "image_url": normalized_image_url,
                "edit_prompt": normalized_edit_prompt,
                "edit_mode": normalized_edit_mode,
            }
