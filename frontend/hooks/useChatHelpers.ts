/**
 * useChat 私有辅助函数集合（AutoResearch + stream update merger）。
 *
 * 1:1 抽离自 `useChat.ts` L36-226（< 800 行合规拆分）。
 * 仅 useChat hook 使用；export 以便单元测试访问。
 */

import { Message, Role, ToolCall, ToolResult } from '../types/types';
import type { StreamUpdate } from './handlers/types';

export const AUTO_RESEARCH_CONTEXT_WINDOW = 6;
export const AUTO_RESEARCH_EVIDENCE_WINDOW = 20;

export type AutoResearchLeadRole = 'selection' | 'ads' | 'listing';

export const AUTO_RESEARCH_PERSONA_LEAD_BY_ID: Record<string, AutoResearchLeadRole> = {
  'amazon-selection-strategist': 'selection',
  'amazon-ads-keyword-operator': 'ads',
  'amazon-listing-cvr-optimizer': 'listing',
};

export const resolvePersonaKey = (personaId?: string): string => {
  if (!personaId) return '';
  const trimmed = personaId.trim();
  if (!trimmed) return '';
  if (!trimmed.includes(':')) return trimmed;
  return trimmed.split(':').pop()?.trim() || trimmed;
};

export const resolveLeadRoleByPersona = (personaId?: string): AutoResearchLeadRole => {
  const key = resolvePersonaKey(personaId);
  return AUTO_RESEARCH_PERSONA_LEAD_BY_ID[key] || 'selection';
};

export const describeLeadRole = (role: AutoResearchLeadRole): string => {
  if (role === 'ads') {
    return '广告与关键词主导（B主导，A/C联动）';
  }
  if (role === 'listing') {
    return 'Listing转化主导（C主导，A/B联动）';
  }
  return '选品策略主导（A主导，B/C联动）';
};

export const summarizeToolEvidenceForAutoResearch = (
  toolCalls?: ReadonlyArray<ToolCall>,
  toolResults?: ReadonlyArray<ToolResult>
): string => {
  const calls = toolCalls || [];
  const results = toolResults || [];
  if (calls.length === 0 && results.length === 0) {
    return '无工具调用记录（可能未启用 MCP 或工具未触发）。';
  }

  const callById = new Map<string, ToolCall>();
  for (const call of calls) {
    callById.set(call.id, call);
  }

  const lines: string[] = [];
  lines.push(`工具调用数: ${calls.length}`);
  lines.push(`工具结果数: ${results.length}`);

  const recentResults = results.slice(-AUTO_RESEARCH_EVIDENCE_WINDOW);
  for (let index = 0; index < recentResults.length; index += 1) {
    const result = recentResults[index];
    const call = callById.get(result.callId);
    const toolName = call?.name || result.name || 'unknown_tool';
    const argsText = call?.arguments ? JSON.stringify(call.arguments, null, 0).slice(0, 280) : '{}';
    const rawResult =
      typeof result.result === 'string'
        ? result.result
        : JSON.stringify(result.result ?? {}, null, 0);
    const resultText = (rawResult || '').slice(0, 420);
    const status = result.error ? `失败: ${result.error}` : '成功';
    lines.push(
      [
        `- [${index + 1}] ${toolName}`,
        `  call_id=${result.callId || 'unknown'}`,
        `  参数=${argsText}`,
        `  状态=${status}`,
        `  摘要=${resultText || '(空结果)'}`,
      ].join('\n')
    );
  }

  if (results.length > recentResults.length) {
    lines.push(`（仅展示最近 ${recentResults.length} 条工具结果，共 ${results.length} 条）`);
  }

  return lines.join('\n');
};

export const summarizeContextForAutoResearch = (history: Message[]): string => {
  const sliced = history.slice(-AUTO_RESEARCH_CONTEXT_WINDOW);
  if (sliced.length === 0) return '无';

  return sliced
    .map((message) => {
      const role =
        message.role === Role.USER ? '用户' : message.role === Role.MODEL ? '助手' : '系统';
      const content = (message.content || '').trim();
      const preview = content.length > 280 ? `${content.slice(0, 280)}...` : content;
      return `[${role}] ${preview || '(空内容)'}`;
    })
    .join('\n');
};

export const buildAutoDeepResearchPrompt = (
  userQuestion: string,
  chatAnswer: string,
  contextSummary: string,
  leadRole: AutoResearchLeadRole,
  personaId: string | undefined,
  toolEvidenceSummary: string
): string => {
  const personaKey = resolvePersonaKey(personaId) || '未指定';
  const leadRoleText = describeLeadRole(leadRole);
  return [
    '你正在执行自动深挖的第二阶段（Deep Research）。',
    '该流程是单次输入触发，你必须在一次响应内完成跨角色联动分析，不允许拆分为多轮提问。',
    '',
    '流程上下文（已完成）：',
    '1) MCP 工具采集（产品/关键词/趋势/排名等）',
    '2) Chat 阶段整理与初步判断',
    '3) 你当前接手：Deep Research 纵深分析与执行方案',
    '',
    '联动规则（强制）：',
    '1. 采用 A/B/C 三角色串联并在单次响应中融合：',
    '   A=选品与市场结构，B=广告与关键词流量，C=Listing与转化优化。',
    `2. 主导视角：${leadRoleText}（来源 persona=${personaKey}）。`,
    '3. 先做证据校验，再给策略，不得直接跳到建议。',
    '4. 必须区分：事实（工具证据）/推断（有不确定性）/执行动作（可落地）。',
    '5. 如数据不足，明确指出缺口与下一步 MCP 补采动作。',
    '',
    '输出格式（强制）：',
    '## 1. 事实核验与不确定性',
    '## 2. A/B/C 串联诊断（产品-关键词-流量-转化-竞争）',
    '## 3. 14/30/90 天执行计划（按优先级）',
    '## 4. KPI 看板（目标值/当前值/阈值/预警）',
    '## 5. 风险、假设与下一步数据补采',
    '',
    `用户原始问题：\n${userQuestion || '(空问题)'}`,
    '',
    `最近会话摘要：\n${contextSummary || '无'}`,
    '',
    `Phase1-Chat 整理结果（待深挖）：\n${chatAnswer || '(空回答)'}`,
    '',
    `Phase1-MCP 工具证据摘要：\n${toolEvidenceSummary}`,
  ].join('\n');
};

export const combineAutoDeepResearchContent = (
  chatContent: string,
  deepResearchContent: string
): string => {
  return [
    chatContent || '',
    '',
    '---',
    '',
    '## Deep Research 深挖补充',
    '',
    deepResearchContent || '',
  ].join('\n');
};

export const STREAM_UPDATE_BATCH_INTERVAL_MS = 32;

export type ModelMessageUpdater = (message: Message) => Message;

export const composeModelMessageUpdaters = (
  previousUpdater: ModelMessageUpdater | null,
  nextUpdater: ModelMessageUpdater
): ModelMessageUpdater => {
  if (!previousUpdater) return nextUpdater;
  return (message) => nextUpdater(previousUpdater(message));
};

export const applyStreamUpdateToModelMessage = (
  message: Message,
  update: StreamUpdate
): Message => {
  return {
    ...message,
    content: update.content || message.content,
    attachments: update.attachments || message.attachments,
    groundingMetadata: update.groundingMetadata,
    urlContextMetadata: update.urlContextMetadata,
    browserOperationId: update.browserOperationId,
    toolCalls: update.toolCalls || message.toolCalls,
    toolResults: update.toolResults || message.toolResults,
    thoughts: update.thoughts || message.thoughts,
    textResponse: Object.prototype.hasOwnProperty.call(update, 'textResponse')
      ? update.textResponse
      : message.textResponse,
    responseKind: update.responseKind || message.responseKind,
    researchStatus: update.researchStatus || message.researchStatus,
    researchInteractionId: update.researchInteractionId || message.researchInteractionId,
    researchRequiredAction: Object.prototype.hasOwnProperty.call(update, 'researchRequiredAction')
      ? update.researchRequiredAction
      : message.researchRequiredAction,
  };
};
