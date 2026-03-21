# Advanced Feature And Module Research

## Input Baseline

- Source docs reviewed:
  - `docs/project-overview.md`
  - `docs/repo-structure-map.md`
  - `docs/self-research.md`
  - `docs/requirements.md`
  - `docs/design.md`

## Candidate Upgrades

| Candidate | Type | Combined Existing Capabilities | Research Evidence | User Value | Engineering Cost | Risk |
| --- | --- | --- | --- | --- | --- | --- |
| Video mode capability split | module / feature | current `video-gen` + backend controls catalog + coordinator | `veo-studio` shows clear capability buckets | high | medium | medium |
| Styling prompt hardening pack | feature | storyboard prompt + reference image + identity-lock prompt patterns | `fit-check` prompt discipline | high | medium | medium |
| Video history metadata refinement | hardening | current session/history + result metadata | current `VideoGenView` history rendering | medium | low | low |

## Selected Expansion

- Expansion name: Video mode capability split
- Expansion type: module-hardening
- Included capabilities:
  - backend-defined capability families
  - schema-driven frontend mode rendering
- Excluded capabilities:
  - workflow video templates
  - new provider integrations
- Why this combination is highest impact: 它能同时改善可维护性、扩展性和用户理解成本。
- Which user workflow or architectural boundary it expands: 从“单页堆参数”扩展为“能力清晰的视频模式产品面”。

## Delivery Plan

1. 先收 backend contract
2. 再收 frontend mode split
3. 补 targeted tests 和 live evidence
4. reviewer gate 后再决定是否扩到 workflow

## Acceptance Criteria

1. backend contract 明确表达能力边界
2. frontend 不再定义隐藏的视频能力语义
3. 历史与结果展示不因 contract 收敛而退化
