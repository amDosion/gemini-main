/**
 * Multi-agent 节点属性面板的 Sheet Stage 协议可视化区域。
 *
 * 1:1 抽离自 `PropertiesPanel.tsx` L201-375
 * （JIRA-frontend-view-decomposition.md P0 #1 Step 5）。
 *
 * 渲染：
 * - 协议有效 → 状态徽章 + session/阶段信息 + 时间线 + artifact 回放引用 + precheck issues
 * - 协议无效 → 结构错误提示 + 解析告警
 * - 未检测到协议 → 不渲染
 */

import React from 'react';
import { AdkExportPanel } from '../AdkExportPanel';
import {
  type SheetStageName,
  type SheetStageProtocolState,
  type SheetStageStatus,
} from '../sheetStageService';

const SHEET_STAGE_LABELS: Record<SheetStageName, string> = {
  ingest: 'Ingest',
  profile: 'Profile',
  query: 'Query',
  export: 'Export',
};

const SHEET_STAGE_RELATION_LABELS: Record<'input' | 'output' | 'history', string> = {
  input: '输入',
  output: '输出',
  history: '历史',
};

const getSheetStageStatusLabel = (status: SheetStageStatus): string =>
  status === 'completed' ? '完成' : '失败';

const getSheetStageStatusClassName = (status: SheetStageStatus): string =>
  status === 'completed'
    ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
    : 'border-red-500/30 bg-red-500/10 text-red-300';

const formatSheetStageTime = (timestampMs: number): string => {
  if (!Number.isFinite(timestampMs) || timestampMs <= 0) {
    return '时间未知';
  }
  try {
    return new Date(timestampMs).toLocaleString();
  } catch {
    return String(timestampMs);
  }
};

export interface PropertiesPanelSheetStageSectionProps {
  stageState: SheetStageProtocolState;
}

export const PropertiesPanelSheetStageSection: React.FC<PropertiesPanelSheetStageSectionProps> = ({
  stageState,
}) => {
  if (!stageState.found) {
    return null;
  }

  if (!stageState.valid || !stageState.envelope) {
    return (
      <div className="pt-1 border-t border-slate-800 space-y-1.5">
        <label className="block text-xs text-slate-500">Sheet Stage 协议</label>
        <div className="rounded border border-red-500/30 bg-red-500/10 p-2 text-[11px] text-red-200 space-y-1">
          <div className="font-medium">检测到协议响应，但结构无效</div>
          {stageState.parseErrors.length > 0 ? (
            <ul className="space-y-0.5 list-disc pl-4">
              {stageState.parseErrors.slice(0, 5).map((item) => (
                <li key={`${item.sourcePath}-${item.message}`}>
                  {item.message} <span className="text-red-300/70">({item.sourcePath})</span>
                </li>
              ))}
            </ul>
          ) : (
            <div>请检查后端响应是否符合 `sheet-stage/v1` 合同。</div>
          )}
        </div>
      </div>
    );
  }

  const { envelope } = stageState;
  return (
    <div className="pt-1 border-t border-slate-800 space-y-2.5">
      <label className="block text-xs text-slate-500">Sheet Stage 协议</label>
      <div className="rounded-lg border border-cyan-500/25 bg-cyan-500/5 p-2.5 space-y-1.5">
        <div className="flex items-center justify-between gap-2">
          <div className="text-[11px] text-cyan-200">协议版本: {envelope.protocolVersion}</div>
          <span
            className={`inline-flex items-center rounded border px-1.5 py-0.5 text-[10px] ${getSheetStageStatusClassName(envelope.status)}`}
          >
            {getSheetStageStatusLabel(envelope.status)}
          </span>
        </div>
        <div className="text-[11px] text-slate-300">
          当前阶段: {SHEET_STAGE_LABELS[envelope.stage]} · Session: {envelope.sessionId}
        </div>
        {envelope.nextStage && (
          <div className="text-[10px] text-slate-400">
            下一阶段: {SHEET_STAGE_LABELS[envelope.nextStage]}
          </div>
        )}
        {envelope.error?.message && (
          <div className="text-[10px] text-red-300">
            错误: {envelope.error.code ? `${envelope.error.code} - ` : ''}
            {envelope.error.message}
          </div>
        )}
      </div>

      {stageState.timeline.length > 0 && (
        <div className="rounded border border-slate-800 bg-slate-900/40 p-2.5">
          <div className="text-[11px] text-slate-300 font-medium mb-1.5">阶段时间线</div>
          <ol className="space-y-1.5" aria-label="Sheet stage timeline">
            {stageState.timeline.map((entry, index) => (
              <li
                key={entry.id}
                className="rounded border border-slate-800 bg-slate-900/50 px-2 py-1.5 text-[10px] text-slate-300 space-y-0.5"
              >
                <div className="flex items-center justify-between gap-2">
                  <span>
                    {index + 1}. {SHEET_STAGE_LABELS[entry.stage]}
                  </span>
                  <span
                    className={`inline-flex items-center rounded border px-1.5 py-0.5 ${getSheetStageStatusClassName(entry.status)}`}
                  >
                    {getSheetStageStatusLabel(entry.status)}
                  </span>
                </div>
                <div className="text-slate-500">
                  时间: {formatSheetStageTime(entry.timestampMs)}
                </div>
                {entry.artifact && (
                  <div className="font-mono text-slate-400 break-all">
                    {entry.artifact.artifactKey}@{entry.artifact.artifactVersion} (
                    {entry.artifact.artifactSessionId})
                  </div>
                )}
              </li>
            ))}
          </ol>
        </div>
      )}

      {stageState.playbackRefs.length > 0 && (
        <div className="rounded border border-slate-800 bg-slate-900/40 p-2.5">
          <div className="text-[11px] text-slate-300 font-medium mb-1.5">Artifact 回放引用</div>
          <ul className="space-y-1.5" aria-label="Sheet stage artifact playback references">
            {stageState.playbackRefs.map((entry) => (
              <li
                key={entry.id}
                className="rounded border border-slate-800 bg-slate-900/50 px-2 py-1.5 text-[10px] text-slate-300 space-y-0.5"
              >
                <div className="flex items-center justify-between gap-2">
                  <span>
                    {SHEET_STAGE_RELATION_LABELS[entry.relation]} ·{' '}
                    {SHEET_STAGE_LABELS[entry.stage]}
                  </span>
                  {entry.timestampMs > 0 && (
                    <span className="text-slate-500">
                      {formatSheetStageTime(entry.timestampMs)}
                    </span>
                  )}
                </div>
                <div className="font-mono text-slate-400 break-all">
                  {entry.artifact.artifactKey}@{entry.artifact.artifactVersion} (
                  {entry.artifact.artifactSessionId})
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {stageState.precheckIssues.length > 0 && (
        <AdkExportPanel issues={stageState.precheckIssues} />
      )}

      {stageState.parseErrors.length > 0 && (
        <div className="rounded border border-amber-500/30 bg-amber-500/10 p-2 text-[10px] text-amber-200 space-y-0.5">
          <div className="font-medium">解析告警</div>
          {stageState.parseErrors.slice(0, 4).map((item) => (
            <div key={`${item.sourcePath}-${item.message}`}>
              {item.message} <span className="text-amber-300/70">({item.sourcePath})</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
