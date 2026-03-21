# MCP 官方研究结论（2026-03-03）

## 1. 研究范围
本结论聚焦以下问题：
- MCP 在官方生态中的推荐接入方式是什么。
- 对话/工具调用链里，结果结构化应该放在前端还是后端。
- 我们项目中 `MCP 管理页 + 运行时调用` 应该如何收敛到统一协议。

## 2. 官方资料来源
- Google Gemini Interactions 文档：
  - <https://ai.google.dev/gemini-api/docs/interactions>
- Interactions API 参考（含 remote MCP 字段定义）：
  - <https://ai.google.dev/api/interactions-api>
- Google GenAI Python SDK（官方仓库，含 MCP 相关能力说明）：
  - <https://github.com/googleapis/python-genai>
- Google Cookbook（Interactions Quickstart，含 Remote MCP 入口）：
  - <https://github.com/google-gemini/cookbook/blob/main/quickstarts/Get_started_interactions_api.ipynb>

## 3. 官方结论（与本项目直接相关）

### 3.1 MCP 接入形态：stdio + remote HTTP 都是官方路径
- 本地/进程型工具用 `stdio`（典型命令为 `npx` / `uvx` 启动）。
- 远程托管工具用 `streamableHttp` / HTTP endpoint（`url` 指向 MCP 服务地址）。
- 这与我们前端「新增/导入/导出全部 JSON 化」的方向一致。

### 3.2 工具是“按服务器动态发现”的，不应前端硬编码大量字段
- 官方链路强调：模型/客户端根据 MCP server 返回的 tool schema 做调用。
- 因此前端不应该直接耦合 raw 的 provider 特定字段（否则每个 MCP 都要写一套前端适配）。

### 3.3 结构化归一应后端做，前端只消费稳定 contract
- 官方示例强调工具调用后要把结果收敛为可消费结构。
- 在我们项目里，后端最适合做“统一 normalization + provider/tool 规则映射”，前端只渲染 `normalized`。

### 3.4 多用户隔离是必需项
- MCP 连接与配置必须按用户隔离（避免同名 serverId 冲突、调用串线）。
- 连接管理应采用连接池/复用策略，避免重复建连和跨用户污染。

## 4. 项目落地决策

### 4.1 配置协议（JSON-first）
- 新增 / 编辑 / 导入 / 导出全部围绕 JSON。
- 标准支持：
  - `type: "stdio"` + `command/args/env`（如 `npx`、`uvx`）。
  - `type: "streamableHttp"` + `url`。

### 4.2 结果协议（normalized-only）
- Runtime 执行接口默认返回 `normalized`。
- `raw result` 仅作为可选调试字段，不作为前端渲染输入。

### 4.3 Sorftime 工具级结构化映射
- 不再仅做“通用 JSON 提取”，而是按工具名细分映射。
- 例如 trend 类工具统一转换为标准 `timeSeries`：
  - `kind: "timeSeries"`
  - `metric`
  - `dimension`
  - `series[]`
  - `points[]`
- 其他工具按 `reviewList` / `table` 等结构输出。

## 5. 为什么要这么做（核心收益）
- 前端稳定：不再跟随第三方 raw 字段波动。
- 复用能力强：不同 MCP provider 可复用同一渲染组件。
- 可观测：后端可统一记录 provider/tool 级别的 normalized 结果质量。
- 可扩展：新增工具映射只改后端规则，不改前端协议。

## 6. Sorftime 示例（推荐 JSON）
```json
{
  "mcpServers": {
    "streamable-http-example": {
      "type": "streamableHttp",
      "url": "https://mcp.sorftime.com?key=YOUR_KEY",
      "name": "Sorftime MCP",
      "description": "Sorftime 跨境电商平台数据服务"
    }
  }
}
```
