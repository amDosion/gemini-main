"""
Shared prompt enrichment for starter workflow nodes, seed agents, and personas.
"""

from __future__ import annotations

import copy
import re
from typing import Any, Dict, List, Sequence


_FINAL_NODE_HINTS = (
    "final",
    "summary",
    "report",
    "review",
    "qa",
    "validate",
    "decision",
    "deliver",
    "audit",
    "最终",
    "总结",
    "汇总",
    "报告",
    "审校",
    "审阅",
    "质检",
    "校验",
    "决策",
    "交付",
)


def _contains_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text or ""))


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_token(value: Any) -> str:
    text = _clean_text(value).lower()
    return re.sub(r"[\s_]+", "-", text)


def _task_specific_expectation(task_type: str, language: str, is_final_node: bool) -> str:
    token = _normalize_token(task_type)
    if language == "zh":
        if token in {"data-analysis", "table-analysis", "sheet-analysis"}:
            return (
                "输出时必须区分“事实/判断/建议”，给出关键指标、异常或相关性依据，并标注样本不足或口径风险。"
            )
        if token in {"image-gen", "image-generate"}:
            return (
                "输出可直接执行的图片生成方案，明确主体、场景、镜头、光线、风格、禁用元素和交付标准。"
            )
        if token in {"image-edit", "image-chat-edit"}:
            return (
                "输出可直接执行的图像编辑方案，明确必须保留的主体特征、禁止修改项、版式安全区和合规风险。"
            )
        if token in {"vision-understand", "image-understand", "vision-analyze"}:
            return (
                "只依据可见视觉证据下结论；不确定信息标记为 unknown，并明确可保留元素、风险点和下一步建议。"
            )
        if token == "video-gen":
            return (
                "输出适合直接生成视频的镜头脚本：主体、动作、场景、镜头运动、节奏、时长、风格和负面约束都要明确。"
            )
        if token == "audio-gen":
            return (
                "输出可直接用于旁白或语音生成的最终文本，并补充语速、停顿、语气、重音或情绪建议。"
            )
        if is_final_node:
            return "你负责汇总多个上游结果，只保留证据充分、可执行、可交付的结论。"
        return "输出时给出结论、依据、风险和下一步动作，不要只复述输入。"

    if token in {"data-analysis", "table-analysis", "sheet-analysis"}:
        return (
            "Separate facts, inference, and actions. Cite the supporting fields or metrics and flag any sample-size or definition risk."
        )
    if token in {"image-gen", "image-generate"}:
        return (
            "Produce an execution-ready image generation brief with subject, scene, camera, lighting, style, constraints, and negative elements."
        )
    if token in {"image-edit", "image-chat-edit"}:
        return (
            "Produce an execution-ready edit brief that preserves product identity, names protected elements, layout safe zones, and compliance constraints."
        )
    if token in {"vision-understand", "image-understand", "vision-analyze"}:
        return (
            "Use only visible evidence. Mark uncertainty as unknown and return preserved elements, risks, and downstream edit guidance."
        )
    if token == "video-gen":
        return (
            "Produce a generation-ready video brief with subject, motion, scene, camera movement, pacing, duration, style, and negative constraints."
        )
    if token == "audio-gen":
        return (
            "Produce the final narration text plus speaking guidance for pace, pauses, emphasis, emotion, and delivery constraints."
        )
    if is_final_node:
        return "You are the synthesis node. Keep only evidence-backed conclusions that are ready for handoff or execution."
    return "Return conclusions, evidence, risks, and next actions instead of repeating the input."


def _build_workflow_node_prompt(
    *,
    template_name: str,
    template_description: str,
    workflow_type: str,
    category: str,
    tags: Sequence[Any],
    node_kind: str,
    node_label: str,
    node_description: str,
    agent_name: str,
    tool_name: str,
    task_type: str,
    input_mapping: str,
    existing_instructions: str,
) -> str:
    joined_context = " ".join(
        part for part in (
            template_name,
            template_description,
            node_label,
            node_description,
            agent_name,
            tool_name,
            task_type,
            existing_instructions,
        )
        if part
    )
    language = "zh" if _contains_cjk(joined_context) else "en"
    label_text = node_label or agent_name or tool_name or "unnamed-node"
    description_text = node_description or template_description or (
        "负责完成当前节点目标" if language == "zh" else "Complete the current node objective."
    )
    node_identity = agent_name or tool_name or node_kind or "node"
    is_final_node = any(token in f"{label_text} {description_text}".lower() for token in _FINAL_NODE_HINTS)
    tags_text = ", ".join(str(item).strip() for item in tags if str(item).strip())
    expectation = _task_specific_expectation(task_type, language, is_final_node)

    if language == "zh":
        sections: List[str] = [
            f"你是工作流模板《{template_name or '未命名模板'}》中的节点“{label_text}”。",
            "## 节点定位",
            f"- 节点类型：{node_kind or 'agent'}",
            f"- 角色/工具：{node_identity}",
            f"- 工作流类型：{workflow_type or 'graph'}",
            f"- 分类：{category or 'general'}",
            f"- 任务目标：{description_text}",
        ]
        if tags_text:
            sections.append(f"- 模板标签：{tags_text}")
        if task_type:
            sections.append(f"- 任务类型：{task_type}")
        if input_mapping:
            sections.extend([
                "## 输入约束",
                "以下输入映射是你必须优先遵守的上游数据绑定：",
                input_mapping,
            ])
        if existing_instructions:
            sections.extend([
                "## 节点原始要求",
                existing_instructions,
            ])
        sections.extend([
            "## 执行原则",
            "1. 只基于当前节点可见输入、上游结果、工具输出和可验证证据作答；缺失信息要显式说明。",
            "2. 不要擅自改写节点职责，也不要把上游未完成的工作当成既定事实。",
            "3. 如果上游数据彼此冲突，先指出冲突，再说明你选择的依据或保守处理方式。",
            "4. 输出应能直接交给下游节点或人类执行，避免空泛表述。",
            "## 输出合同",
            expectation,
            "请默认保持结构化表达，优先给出结论、证据、风险和下一步动作。",
        ])
        return "\n".join(part for part in sections if part)

    sections = [
        f"You are node \"{label_text}\" inside the workflow template \"{template_name or 'Untitled Template'}\".",
        "## Node Context",
        f"- Node type: {node_kind or 'agent'}",
        f"- Role or tool: {node_identity}",
        f"- Workflow type: {workflow_type or 'graph'}",
        f"- Category: {category or 'general'}",
        f"- Objective: {description_text}",
    ]
    if tags_text:
        sections.append(f"- Template tags: {tags_text}")
    if task_type:
        sections.append(f"- Task type: {task_type}")
    if input_mapping:
        sections.extend([
            "## Input Contract",
            "Respect this upstream binding before making any assumptions:",
            input_mapping,
        ])
    if existing_instructions:
        sections.extend([
            "## Existing Node Instructions",
            existing_instructions,
        ])
    sections.extend([
        "## Operating Rules",
        "1. Use only the current node input, upstream outputs, tool results, and verifiable evidence.",
        "2. Do not silently change the node scope or invent missing upstream work.",
        "3. If inputs conflict, call out the conflict and explain the conservative resolution.",
        "4. Return output that is directly usable by the next node or an operator.",
        "## Output Contract",
        expectation,
        "Prefer a structured answer with conclusion, evidence, risks, and next actions.",
    ])
    return "\n".join(part for part in sections if part)


def enrich_starter_template_definition(definition: Dict[str, Any]) -> Dict[str, Any]:
    enriched = copy.deepcopy(definition)
    config = enriched.get("config")
    if not isinstance(config, dict):
        return enriched

    template_name = _clean_text(enriched.get("name"))
    template_description = _clean_text(enriched.get("description"))
    workflow_type = _clean_text(enriched.get("workflow_type"))
    category = _clean_text(enriched.get("category"))
    tags = enriched.get("tags") if isinstance(enriched.get("tags"), list) else []

    nodes = config.get("nodes")
    if not isinstance(nodes, list):
        return enriched

    for node in nodes:
        if not isinstance(node, dict):
            continue
        data = node.get("data")
        if not isinstance(data, dict):
            continue

        node_kind = _clean_text(data.get("type") or node.get("type")).lower()
        has_prompt_surface = any(
            _clean_text(data.get(key))
            for key in ("instructions", "agentName", "toolName", "agentTaskType", "taskType")
        )
        if node_kind not in {"agent", "tool"} and not has_prompt_surface:
            continue

        data["instructions"] = _build_workflow_node_prompt(
            template_name=template_name,
            template_description=template_description,
            workflow_type=workflow_type,
            category=category,
            tags=tags,
            node_kind=node_kind or "agent",
            node_label=_clean_text(data.get("label")),
            node_description=_clean_text(data.get("description")),
            agent_name=_clean_text(data.get("agentName")),
            tool_name=_clean_text(data.get("toolName")),
            task_type=_clean_text(data.get("agentTaskType") or data.get("taskType")),
            input_mapping=_clean_text(data.get("inputMapping")),
            existing_instructions=_clean_text(data.get("instructions")),
        )

    return enriched


def _build_role_contract(
    *,
    prompt: str,
    role_name: str,
    role_description: str,
    task_type: str,
    category: str,
    language: str,
) -> str:
    expectation = _task_specific_expectation(task_type, language, is_final_node=False)
    if language == "zh":
        sections = [
            prompt,
            "## 通用执行要求",
            f"- 角色名称：{role_name}",
            f"- 角色职责：{role_description or '按当前任务提供专业支持'}",
            f"- 能力域：{category or 'general'}",
            f"- 默认任务类型：{task_type or 'chat'}",
            "- 优先给出可执行结论，再补充依据、风险和后续动作。",
            "- 事实、推断、建议要尽量分开，不要把假设写成已验证结论。",
            "- 输入不足时先指出缺口，再做最小必要假设，并标注假设对结论的影响。",
            "- 输出要直接可交付：代码、文案、策略、表格、提示词或检查清单都要可复用。",
            "## 质量要求",
            expectation,
        ]
        return "\n".join(part for part in sections if part)

    sections = [
        prompt,
        "## Operating Contract",
        f"- Role: {role_name}",
        f"- Responsibility: {role_description or 'Provide domain-specific support for the current task.'}",
        f"- Capability area: {category or 'general'}",
        f"- Default task type: {task_type or 'chat'}",
        "- Lead with an actionable answer, then support it with evidence, risks, and next steps.",
        "- Keep facts, inference, and recommendations clearly separated whenever uncertainty exists.",
        "- If the input is incomplete, identify the missing pieces and make only the minimum necessary assumptions.",
        "- Return deliverables that are immediately reusable by the user or downstream systems.",
        "## Quality Bar",
        expectation,
    ]
    return "\n".join(part for part in sections if part)


def enhance_seed_agents(seeds: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    enhanced: List[Dict[str, Any]] = []
    for seed in seeds:
        item = copy.deepcopy(seed)
        prompt = _clean_text(item.get("system_prompt"))
        joined = " ".join(
            part for part in (
                _clean_text(item.get("name")),
                _clean_text(item.get("description")),
                prompt,
            )
            if part
        )
        language = "zh" if _contains_cjk(joined) else "en"
        task_type = "chat"
        agent_card = item.get("agent_card")
        if isinstance(agent_card, dict):
            defaults = agent_card.get("defaults")
            if isinstance(defaults, dict):
                task_type = _normalize_token(defaults.get("defaultTaskType")) or "chat"
        capability_area = " / ".join(
            part for part in (
                _clean_text(item.get("provider_id")),
                task_type,
            )
            if part
        ) or "general"
        item["system_prompt"] = _build_role_contract(
            prompt=prompt,
            role_name=_clean_text(item.get("name")),
            role_description=_clean_text(item.get("description")),
            task_type=task_type,
            category=capability_area,
            language=language,
        )
        enhanced.append(item)
    return enhanced


def enhance_personas(personas: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    enhanced: List[Dict[str, Any]] = []
    for persona in personas:
        item = copy.deepcopy(persona)
        prompt = _clean_text(item.get("systemPrompt"))
        category = _clean_text(item.get("category"))
        task_type = "chat"
        category_token = category.lower()
        if "image" in category_token:
            task_type = "image-gen"
        elif "coding" in category_token or "tech" in category_token:
            task_type = "chat"
        elif "data" in category_token or "analysis" in category_token:
            task_type = "data-analysis"
        joined = " ".join(
            part for part in (
                _clean_text(item.get("name")),
                _clean_text(item.get("description")),
                prompt,
                category,
            )
            if part
        )
        language = "zh" if _contains_cjk(joined) else "en"
        item["systemPrompt"] = _build_role_contract(
            prompt=prompt,
            role_name=_clean_text(item.get("name")),
            role_description=_clean_text(item.get("description")),
            task_type=task_type,
            category=category,
            language=language,
        )
        enhanced.append(item)
    return enhanced
