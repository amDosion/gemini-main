import React from 'react';
import { Loader2, RefreshCw } from 'lucide-react';
import {
  extractStageReplayContext,
  replayStageFromAnchor,
  type StageReplayAnchor,
  type StageReplayDiffEntry,
} from './stageReplayService';
import {
  createInitialStageReplayState,
  getStageReplayStatusLabel,
  selectStageReplayAnchor,
  stageReplayReducer,
} from './stageReplayReducer';

interface StageReplayPanelProps {
  sessionId: string;
  sessionSnapshot: unknown;
  onReplayCompleted?: () => void;
}

const STATUS_BADGE_CLASS: Record<string, string> = {
  idle: 'border-slate-700 text-slate-300 bg-slate-800/60',
  snapshot_invalid: 'border-red-500/30 text-red-200 bg-red-500/10',
  ready: 'border-cyan-500/30 text-cyan-200 bg-cyan-500/10',
  replaying: 'border-amber-500/30 text-amber-200 bg-amber-500/10',
  succeeded: 'border-emerald-500/30 text-emerald-200 bg-emerald-500/10',
  failed: 'border-red-500/30 text-red-200 bg-red-500/10',
};

const formatArtifact = (anchor: StageReplayAnchor): string =>
  `${anchor.artifact.artifactKey}@${anchor.artifact.artifactVersion} (${anchor.artifact.artifactSessionId})`;

const formatJson = (value: unknown): string => {
  if (value === undefined) {
    return '<undefined>';
  }
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
};

const getDiffTagClass = (change: StageReplayDiffEntry['change']): string => {
  if (change === 'added') {
    return 'border-emerald-500/30 bg-emerald-500/10 text-emerald-200';
  }
  if (change === 'removed') {
    return 'border-red-500/30 bg-red-500/10 text-red-200';
  }
  return 'border-amber-500/30 bg-amber-500/10 text-amber-200';
};

const getDiffLabel = (change: StageReplayDiffEntry['change']): string => {
  if (change === 'added') return '新增';
  if (change === 'removed') return '移除';
  return '变更';
};

export const StageReplayPanel: React.FC<StageReplayPanelProps> = ({
  sessionId,
  sessionSnapshot,
  onReplayCompleted,
}) => {
  const [state, dispatch] = React.useReducer(stageReplayReducer, undefined, createInitialStageReplayState);
  const replayAbortRef = React.useRef<AbortController | null>(null);

  React.useEffect(() => {
    const context = extractStageReplayContext(sessionSnapshot, sessionId);
    dispatch({ type: 'hydrate_context', context });
  }, [sessionSnapshot, sessionId]);

  React.useEffect(() => {
    return () => {
      replayAbortRef.current?.abort();
    };
  }, []);

  const selectedAnchor = React.useMemo(() => selectStageReplayAnchor(state), [state]);

  const handleReplay = React.useCallback(async () => {
    dispatch({ type: 'start_replay' });

    if (!state.context?.valid || !selectedAnchor || !selectedAnchor.canReplay) {
      return;
    }

    replayAbortRef.current?.abort();
    const controller = new AbortController();
    replayAbortRef.current = controller;

    try {
      const result = await replayStageFromAnchor(state.context, selectedAnchor.id, controller.signal);
      dispatch({ type: 'replay_succeeded', result });
      onReplayCompleted?.();
    } catch (error) {
      if (controller.signal.aborted) {
        return;
      }
      const message = error instanceof Error ? error.message : '阶段回放失败';
      dispatch({ type: 'replay_failed', errorMessage: message });
    }
  }, [state.context, selectedAnchor, onReplayCompleted]);

  const canRunReplay =
    state.status !== 'replaying'
    && Boolean(state.context?.valid)
    && Boolean(selectedAnchor?.canReplay);

  return (
    <div className="p-3 rounded border border-slate-800 bg-slate-900/40 space-y-3">
      <div className="flex items-center justify-between gap-2">
        <div className="text-xs text-slate-300 font-medium">历史 Session Stage Replay</div>
        <span
          data-testid="stage-replay-status"
          className={`inline-flex items-center rounded border px-2 py-0.5 text-[10px] ${STATUS_BADGE_CLASS[state.status] || STATUS_BADGE_CLASS.idle}`}
        >
          {getStageReplayStatusLabel(state.status)}
        </span>
      </div>

      {state.context?.message && (
        <div className="text-[11px] text-slate-400">{state.context.message}</div>
      )}

      {state.status === 'snapshot_invalid' && (
        <div className="rounded border border-red-500/30 bg-red-500/10 p-2 text-[11px] text-red-200 space-y-1">
          <div className="font-medium">回放已被禁用（fail-closed）</div>
          <div>{state.errorMessage || '历史会话数据不完整，无法安全执行回放。'}</div>
          {state.context?.parseErrors?.length ? (
            <ul className="list-disc pl-4 space-y-0.5">
              {state.context.parseErrors.slice(0, 4).map((item) => (
                <li key={`${item.sourcePath}-${item.message}`}>
                  {item.message} <span className="text-red-300/70">({item.sourcePath})</span>
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      )}

      {state.context?.timeline.length ? (
        <div className="rounded border border-slate-800 bg-slate-950/40 p-2.5">
          <div className="text-[11px] text-slate-300 font-medium mb-1.5">历史阶段时间线</div>
          <ol className="space-y-1.5" aria-label="Stage replay timeline">
            {state.context.timeline.map((entry, index) => (
              <li key={entry.id} className="rounded border border-slate-800 bg-slate-900/50 px-2 py-1.5 text-[10px] text-slate-300 space-y-0.5">
                <div className="flex items-center justify-between gap-2">
                  <span>{index + 1}. {entry.stage}</span>
                  <span className="text-slate-500">{entry.status}</span>
                </div>
                {entry.artifact && (
                  <div className="font-mono text-slate-400 break-all">
                    {entry.artifact.artifactKey}@{entry.artifact.artifactVersion}
                  </div>
                )}
              </li>
            ))}
          </ol>
        </div>
      ) : null}

      <div className="rounded border border-slate-800 bg-slate-950/40 p-2.5 space-y-2">
        <div className="text-[11px] text-slate-300 font-medium">Replay 锚点选择</div>
        {state.context?.anchors.length ? (
          <>
            <select
              aria-label="Replay anchor"
              value={state.selectedAnchorId}
              onChange={(event) => dispatch({ type: 'select_anchor', anchorId: event.target.value })}
              className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200"
            >
              {state.context.anchors.map((anchor) => (
                <option key={anchor.id} value={anchor.id}>
                  {anchor.stageLabel} · v{anchor.artifact.artifactVersion} · {anchor.timestampLabel}{anchor.canReplay ? '' : ' · 不可回放'}
                </option>
              ))}
            </select>

            {selectedAnchor && (
              <div className="rounded border border-slate-800 bg-slate-900/60 p-2 text-[11px] text-slate-300 space-y-1">
                <div>阶段: {selectedAnchor.stageLabel}</div>
                <div>Artifact: <span className="font-mono text-slate-400 break-all">{formatArtifact(selectedAnchor)}</span></div>
                <div>Invocation: <span className="font-mono text-slate-400">{selectedAnchor.invocationId || '-'}</span></div>
                {selectedAnchor.inputArtifact && (
                  <div>
                    输入 Artifact:
                    <span className="ml-1 font-mono text-slate-400 break-all">
                      {selectedAnchor.inputArtifact.artifactKey}@{selectedAnchor.inputArtifact.artifactVersion}
                    </span>
                  </div>
                )}
                {!selectedAnchor.canReplay && (
                  <div className="rounded border border-amber-500/30 bg-amber-500/10 px-2 py-1 text-amber-200">
                    {selectedAnchor.blockedReason}
                  </div>
                )}
              </div>
            )}
          </>
        ) : (
          <div className="text-[11px] text-slate-500">未生成可选锚点。</div>
        )}

        <button
          type="button"
          onClick={() => {
            void handleReplay();
          }}
          disabled={!canRunReplay}
          className="w-full px-2.5 py-1.5 text-xs rounded border border-indigo-500/40 bg-indigo-500/15 text-indigo-200 hover:bg-indigo-500/25 disabled:opacity-50 inline-flex items-center justify-center gap-1"
        >
          {state.status === 'replaying' ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
          {state.status === 'replaying' ? '回放中...' : '执行 Stage 回放'}
        </button>

        {state.errorMessage && state.status !== 'snapshot_invalid' && (
          <div className={`text-[11px] rounded border px-2 py-1.5 ${
            state.status === 'failed'
              ? 'border-red-500/30 bg-red-500/10 text-red-200'
              : 'border-amber-500/30 bg-amber-500/10 text-amber-200'
          }`}>
            {state.errorMessage}
          </div>
        )}
      </div>

      {state.status === 'succeeded' && state.result && (
        <div className="rounded border border-emerald-500/30 bg-emerald-500/10 p-2.5 space-y-2">
          <div className="flex items-center justify-between gap-2">
            <div className="text-[11px] text-emerald-200 font-medium">回放完成</div>
            <button
              type="button"
              onClick={() => dispatch({ type: 'clear_feedback' })}
              className="text-[10px] px-1.5 py-0.5 rounded border border-emerald-500/40 text-emerald-200 hover:bg-emerald-500/20"
            >
              清除结果
            </button>
          </div>
          <div className="text-[10px] text-emerald-100/90">
            新 Artifact: {state.result.replayEnvelope.artifact
              ? `${state.result.replayEnvelope.artifact.artifactKey}@${state.result.replayEnvelope.artifact.artifactVersion}`
              : '-'}
          </div>

          <div className="rounded border border-slate-800 bg-slate-950/60 p-2 space-y-1">
            <div className="text-[11px] text-slate-300 font-medium">原始 vs 回放 差异</div>
            {state.result.diff.length === 0 ? (
              <div className="text-[11px] text-slate-400">回放输出与原始输出一致（无差异）。</div>
            ) : (
              <ul className="space-y-1" aria-label="Stage replay diff list">
                {state.result.diff.slice(0, 20).map((entry) => (
                  <li key={`${entry.path}-${entry.change}`} className="rounded border border-slate-800 bg-slate-900/50 p-1.5 space-y-0.5 text-[10px]">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-slate-300 break-all">{entry.path}</span>
                      <span className={`inline-flex items-center rounded border px-1 py-0.5 ${getDiffTagClass(entry.change)}`}>
                        {getDiffLabel(entry.change)}
                      </span>
                    </div>
                    <div className="text-slate-500">before: {entry.originalPreview}</div>
                    <div className="text-slate-400">after: {entry.replayedPreview}</div>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div className="rounded border border-slate-800 bg-slate-950/60 p-2">
              <div className="text-[10px] text-slate-400 mb-1">Original payload</div>
              <pre className="text-[10px] text-slate-300 whitespace-pre-wrap break-all max-h-[160px] overflow-auto">
                {formatJson(state.result.originalPayload)}
              </pre>
            </div>
            <div className="rounded border border-slate-800 bg-slate-950/60 p-2">
              <div className="text-[10px] text-slate-400 mb-1">Replayed payload</div>
              <pre className="text-[10px] text-slate-300 whitespace-pre-wrap break-all max-h-[160px] overflow-auto">
                {formatJson(state.result.replayedPayload)}
              </pre>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default StageReplayPanel;
