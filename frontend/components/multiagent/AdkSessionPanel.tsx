import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Check, Loader2, RefreshCw, Undo2, X } from 'lucide-react';
import type { AgentDef } from './types';
import {
  AdkApprovalTicket,
  AdkConfirmCandidate,
  AdkSessionItem,
  confirmAdkToolCall,
  extractAdkConfirmActionSupport,
  extractAdkConfirmCandidates,
  extractAdkExportPrecheckIssues,
  extractAdkRuntimePolicyState,
  formatAdkConfirmToolErrorMessage,
  getAdkAgentSession,
  isAdkNonceExpired,
  listAdkAgentSessions,
  parseAdkTimestampMs,
  rewindAdkSession,
} from './adkSessionService';
import { AdkExportPanel } from './AdkExportPanel';
import { AdkRuntimePolicyPanel } from './AdkRuntimePolicyPanel';
import { StageReplayPanel } from './StageReplayPanel';

interface AdkSessionPanelProps {
  agent: AgentDef;
  onClose: () => void;
}

const formatTimestamp = (value: unknown): string => {
  const raw = Number(value);
  if (!Number.isFinite(raw) || raw <= 0) return '-';
  return new Date(raw).toLocaleString();
};

const parseOptionalJson = (text: string): unknown => {
  const raw = String(text || '').trim();
  if (!raw) return undefined;
  return JSON.parse(raw);
};

const formatJsonForEditor = (value: unknown): string => {
  if (value === undefined || value === null) return '';
  if (typeof value === 'string') {
    const raw = value.trim();
    if (!raw) return '';
    try {
      const parsed = JSON.parse(raw);
      return JSON.stringify(parsed, null, 2);
    } catch {
      return JSON.stringify(value, null, 2);
    }
  }
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return '';
  }
};

const formatNonceExpiry = (value: string): string => {
  const normalized = String(value || '').trim();
  if (!normalized) return '-';
  const ts = parseAdkTimestampMs(normalized);
  if (ts <= 0) return normalized;
  return new Date(ts).toLocaleString();
};

export const AdkSessionPanel: React.FC<AdkSessionPanelProps> = ({ agent, onClose }) => {
  const [sessions, setSessions] = useState<AdkSessionItem[]>([]);
  const [loadingSessions, setLoadingSessions] = useState(false);
  const [selectedSessionId, setSelectedSessionId] = useState('');
  const [sessionSnapshot, setSessionSnapshot] = useState<any>(null);
  const [loadingSnapshot, setLoadingSnapshot] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [notice, setNotice] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const [functionCallId, setFunctionCallId] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const [confirmHint, setConfirmHint] = useState('');
  const [confirmPayload, setConfirmPayload] = useState('');
  const [confirmInvocationId, setConfirmInvocationId] = useState('');
  const [confirmTicket, setConfirmTicket] = useState('');
  const [confirmApprovalTicket, setConfirmApprovalTicket] = useState<AdkApprovalTicket | null>(null);
  const [confirmNonce, setConfirmNonce] = useState('');
  const [confirmNonceExpiresAt, setConfirmNonceExpiresAt] = useState('');
  const [confirmTenantId, setConfirmTenantId] = useState('');
  const [selectedConfirmCandidateId, setSelectedConfirmCandidateId] = useState('');
  const [rewindInvocationId, setRewindInvocationId] = useState('');
  const [runtimePolicyDraft, setRuntimePolicyDraft] = useState<{ strategy?: string; strictMode?: boolean }>({});

  const normalizedAgentId = String(agent?.id || '').trim();

  const loadSessions = useCallback(async () => {
    if (!normalizedAgentId) return;
    setLoadingSessions(true);
    setNotice(null);
    try {
      const result = await listAdkAgentSessions(normalizedAgentId);
      setSessions(result);
      if (result.length > 0) {
        setSelectedSessionId((prev) => {
          if (prev && result.some((item) => item.id === prev)) {
            return prev;
          }
          return result[0].id;
        });
      } else {
        setSelectedSessionId('');
        setSessionSnapshot(null);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : '加载会话失败';
      setNotice({ type: 'error', text: message });
    } finally {
      setLoadingSessions(false);
    }
  }, [normalizedAgentId]);

  const loadSessionSnapshot = useCallback(async () => {
    if (!normalizedAgentId || !selectedSessionId) {
      setSessionSnapshot(null);
      return;
    }
    setLoadingSnapshot(true);
    try {
      const snapshot = await getAdkAgentSession(normalizedAgentId, selectedSessionId);
      setSessionSnapshot(snapshot.raw);
    } catch (error) {
      const message = error instanceof Error ? error.message : '加载会话详情失败';
      setNotice({ type: 'error', text: message });
      setSessionSnapshot(null);
    } finally {
      setLoadingSnapshot(false);
    }
  }, [normalizedAgentId, selectedSessionId]);

  useEffect(() => {
    void loadSessions();
  }, [loadSessions]);

  useEffect(() => {
    void loadSessionSnapshot();
  }, [loadSessionSnapshot]);

  const activeSession = useMemo(
    () => sessions.find((item) => item.id === selectedSessionId) || null,
    [sessions, selectedSessionId]
  );
  const confirmCandidates = useMemo<AdkConfirmCandidate[]>(
    () => extractAdkConfirmCandidates(sessionSnapshot),
    [sessionSnapshot]
  );
  const exportPrecheckIssues = useMemo(
    () => extractAdkExportPrecheckIssues(sessionSnapshot),
    [sessionSnapshot]
  );
  const runtimePolicy = useMemo(
    () => extractAdkRuntimePolicyState(sessionSnapshot, {
      selectedStrategy: runtimePolicyDraft.strategy,
      selectedStrictMode: runtimePolicyDraft.strictMode,
    }),
    [sessionSnapshot, runtimePolicyDraft.strategy, runtimePolicyDraft.strictMode]
  );
  const effectiveSelectedConfirmCandidateId = useMemo(() => {
    if (!selectedConfirmCandidateId) {
      return confirmCandidates[0]?.id || '';
    }
    if (confirmCandidates.some((item) => item.id === selectedConfirmCandidateId)) {
      return selectedConfirmCandidateId;
    }
    return confirmCandidates[0]?.id || '';
  }, [confirmCandidates, selectedConfirmCandidateId]);
  const selectedConfirmCandidate = useMemo(
    () => confirmCandidates.find((item) => item.id === effectiveSelectedConfirmCandidateId) || null,
    [confirmCandidates, effectiveSelectedConfirmCandidateId]
  );
  const confirmActionSupport = useMemo(
    () => extractAdkConfirmActionSupport(sessionSnapshot),
    [sessionSnapshot]
  );
  const supportsExplicitReject = confirmActionSupport.supportsExplicitReject;
  const effectiveConfirmed = supportsExplicitReject ? confirmed : true;

  useEffect(() => {
    setRuntimePolicyDraft({});
    setConfirmApprovalTicket(null);
  }, [selectedSessionId]);

  useEffect(() => {
    if (!supportsExplicitReject) {
      setConfirmed(true);
    }
  }, [supportsExplicitReject]);

  const approvalBlockedReason = useMemo(() => {
    if (!effectiveConfirmed) {
      if (!supportsExplicitReject) {
        return '当前后端未声明显式拒绝提交能力，请仅提交批准。';
      }
      return '';
    }

    const normalizedFunctionCallId = functionCallId.trim();
    if (!normalizedFunctionCallId) {
      return '批准时 function_call_id 不能为空。';
    }

    if (
      selectedConfirmCandidate &&
      effectiveSelectedConfirmCandidateId &&
      normalizedFunctionCallId !== selectedConfirmCandidate.id
    ) {
      return '批准时 function_call_id 必须与候选确认项一致，避免票据绑定校验失败。';
    }

    if (!confirmTicket.trim() || !confirmNonce.trim()) {
      return '批准必须携带有效票据：缺少 ticket 或 nonce。';
    }

    if (!confirmInvocationId.trim()) {
      return '批准必须携带 invocation_id，以满足后端票据绑定校验。';
    }

    if (isAdkNonceExpired(confirmNonceExpiresAt)) {
      return '审批票据已过期，请刷新会话并重新填充候选项。';
    }

    return '';
  }, [
    effectiveConfirmed,
    supportsExplicitReject,
    selectedConfirmCandidate,
    effectiveSelectedConfirmCandidateId,
    functionCallId,
    confirmInvocationId,
    confirmTicket,
    confirmNonce,
    confirmNonceExpiresAt,
  ]);

  const handleConfirmTool = useCallback(async () => {
    if (!normalizedAgentId || !selectedSessionId) return;

    if (!functionCallId.trim()) {
      setNotice({ type: 'error', text: 'function_call_id 不能为空' });
      return;
    }

    if (approvalBlockedReason) {
      setNotice({ type: 'error', text: approvalBlockedReason });
      return;
    }

    setSubmitting(true);
    setNotice(null);
    try {
      const payload = parseOptionalJson(confirmPayload);
      const response = await confirmAdkToolCall(normalizedAgentId, selectedSessionId, {
        functionCallId,
        confirmed: effectiveConfirmed,
        hint: confirmHint,
        payload,
        invocationId: confirmInvocationId,
        ticket: confirmTicket,
        approvalTicket: confirmApprovalTicket,
        nonce: confirmNonce,
        nonceExpiresAt: confirmNonceExpiresAt,
        tenantId: confirmTenantId,
        candidateId: effectiveSelectedConfirmCandidateId,
      });
      const invocation = String(response?.invocationId || response?.invocation_id || '').trim();
      const responseConfirmed = (
        typeof response?.confirmed === 'boolean'
          ? response.confirmed
          : effectiveConfirmed
      );
      const action = responseConfirmed ? '批准' : '拒绝';
      setNotice({
        type: 'success',
        text: invocation ? `工具${action}已提交，invocation=${invocation}` : `工具${action}已提交`,
      });
      await loadSessionSnapshot();
      await loadSessions();
    } catch (error) {
      const message = formatAdkConfirmToolErrorMessage(error, '工具确认失败');
      setNotice({ type: 'error', text: message });
    } finally {
      setSubmitting(false);
    }
  }, [
    normalizedAgentId,
    selectedSessionId,
    functionCallId,
    approvalBlockedReason,
    confirmPayload,
    effectiveConfirmed,
    confirmHint,
    confirmInvocationId,
    confirmTicket,
    confirmApprovalTicket,
    confirmNonce,
    confirmNonceExpiresAt,
    confirmTenantId,
    effectiveSelectedConfirmCandidateId,
    loadSessionSnapshot,
    loadSessions,
  ]);

  const handleFillConfirmCandidate = useCallback((candidate: AdkConfirmCandidate | null) => {
    if (!candidate) return;
    setSelectedConfirmCandidateId(candidate.id || '');
    setFunctionCallId(candidate.id || '');
    setConfirmHint(candidate.hint || '');
    setConfirmInvocationId(candidate.invocationId || '');
    setConfirmPayload(formatJsonForEditor(candidate.payload));
    setConfirmTicket(candidate.ticket || '');
    setConfirmApprovalTicket(candidate.approvalTicket || null);
    setConfirmNonce(candidate.nonce || '');
    setConfirmNonceExpiresAt(candidate.nonceExpiresAt || '');
    setConfirmTenantId(candidate.tenantId || '');
  }, []);

  const handleRewind = useCallback(async () => {
    if (!normalizedAgentId || !selectedSessionId) return;
    setSubmitting(true);
    setNotice(null);
    try {
      const response = await rewindAdkSession(normalizedAgentId, selectedSessionId, rewindInvocationId);
      const status = String(response?.status || '').trim() || 'rewound';
      setNotice({ type: 'success', text: `会话回滚成功，status=${status}` });
      await loadSessionSnapshot();
      await loadSessions();
    } catch (error) {
      const message = error instanceof Error ? error.message : '会话回滚失败';
      setNotice({ type: 'error', text: message });
    } finally {
      setSubmitting(false);
    }
  }, [normalizedAgentId, selectedSessionId, rewindInvocationId, loadSessionSnapshot, loadSessions]);

  return (
    <div className="absolute inset-0 z-[70] flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="w-[980px] max-w-[95vw] h-[78vh] rounded-xl border border-slate-700 bg-slate-900 text-slate-200 shadow-2xl overflow-hidden flex flex-col">
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-800">
          <div>
            <div className="text-sm font-semibold">运行时会话管理</div>
            <div className="text-[11px] text-slate-400">{agent.name} · {agent.providerId}/{agent.modelId}</div>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => void loadSessions()}
              disabled={loadingSessions}
              className="px-2.5 py-1.5 text-xs rounded border border-slate-700 bg-slate-800 hover:bg-slate-700 transition-colors disabled:opacity-50 inline-flex items-center gap-1"
            >
              {loadingSessions ? <Loader2 size={12} className="animate-spin" /> : <RefreshCw size={12} />}
              刷新
            </button>
            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded border border-slate-700 bg-slate-800 hover:bg-slate-700 transition-colors"
            >
              <X size={14} />
            </button>
          </div>
        </div>

        {notice && (
          <div className={`mx-4 mt-3 px-3 py-2 rounded border text-xs ${
            notice.type === 'success'
              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
              : 'bg-red-500/10 border-red-500/30 text-red-300'
          }`}>
            {notice.text}
          </div>
        )}

        <div className="flex-1 min-h-0 grid grid-cols-[260px_1fr] gap-0 mt-3">
          <div className="border-r border-slate-800 overflow-y-auto px-3 pb-3">
            <div className="text-[11px] text-slate-500 mb-2">会话列表 ({sessions.length})</div>
            {loadingSessions ? (
              <div className="py-8 flex items-center justify-center text-slate-500">
                <Loader2 size={16} className="animate-spin" />
              </div>
            ) : sessions.length === 0 ? (
              <div className="text-xs text-slate-500 py-4">暂无可用会话</div>
            ) : (
              <div className="space-y-1.5">
                {sessions.map((session) => {
                  const raw = session.raw || {};
                  const updatedAt = raw?.updatedAt || raw?.updated_at || raw?.lastUpdateTime || raw?.last_update_time;
                  return (
                    <button
                      key={session.id}
                      type="button"
                      onClick={() => setSelectedSessionId(session.id)}
                      className={`w-full text-left px-2.5 py-2 rounded border transition-colors ${
                        selectedSessionId === session.id
                          ? 'border-indigo-500/40 bg-indigo-500/15 text-indigo-200'
                          : 'border-slate-700 bg-slate-800/70 text-slate-300 hover:bg-slate-800'
                      }`}
                    >
                      <div className="text-[11px] font-mono truncate">{session.id}</div>
                      <div className="text-[10px] text-slate-500 mt-1">{formatTimestamp(updatedAt)}</div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          <div className="overflow-y-auto px-4 pb-4 space-y-4">
            <AdkRuntimePolicyPanel
              policy={runtimePolicy}
              onChange={(next) => setRuntimePolicyDraft({
                strategy: next.strategy,
                strictMode: next.strictMode,
              })}
            />

            <div className="grid grid-cols-2 gap-3 mt-1">
              <div className="p-3 rounded border border-slate-800 bg-slate-900/40">
                <div className="text-xs text-slate-300 font-medium mb-2">工具确认（confirm-tool）</div>
                <div className="text-[11px] px-2 py-1.5 rounded border border-amber-500/30 bg-amber-500/10 text-amber-200 mb-2">
                  {supportsExplicitReject
                    ? '后端已声明支持显式拒绝；请按候选项与票据提交批准或拒绝。'
                    : '后端当前仅接受显式批准提交；拒绝请保持不提交。'}
                </div>
                <div className="space-y-2">
                  {confirmCandidates.length > 0 ? (
                    <div className="p-2 rounded border border-slate-700/80 bg-slate-800/40 space-y-2">
                      <div className="text-[11px] text-slate-400">候选确认项 ({confirmCandidates.length})</div>
                      <select
                        aria-label="候选确认项列表"
                        value={effectiveSelectedConfirmCandidateId}
                        onChange={(e) => setSelectedConfirmCandidateId(e.target.value)}
                        className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 font-mono"
                      >
                        {confirmCandidates.map((candidate) => (
                          <option key={candidate.id} value={candidate.id}>
                            {candidate.id}{candidate.name ? ` · ${candidate.name}` : ''}
                          </option>
                        ))}
                      </select>
                      <button
                        type="button"
                        onClick={() => handleFillConfirmCandidate(selectedConfirmCandidate)}
                        disabled={!selectedConfirmCandidate}
                        className="w-full px-2 py-1.5 text-xs rounded border border-slate-600 bg-slate-800 hover:bg-slate-700 text-slate-200 disabled:opacity-50"
                      >
                        一键填充候选项
                      </button>
                      {selectedConfirmCandidate && (
                        <div className="text-[10px] text-slate-400 space-y-1">
                          <div>name: {selectedConfirmCandidate.name || '-'}</div>
                          <div>invocation: {selectedConfirmCandidate.invocationId || '-'}</div>
                          <div>ticket: {selectedConfirmCandidate.ticket || '-'}</div>
                          <div>nonce: {selectedConfirmCandidate.nonce || '-'}</div>
                          <div>
                            nonce_expires_at: {formatNonceExpiry(selectedConfirmCandidate.nonceExpiresAt)}
                            {isAdkNonceExpired(selectedConfirmCandidate.nonceExpiresAt) ? '（已过期）' : ''}
                          </div>
                          <div>tenant: {selectedConfirmCandidate.tenantId || '-'}</div>
                          {selectedConfirmCandidate.hint && (
                            <div className="text-slate-300">hint: {selectedConfirmCandidate.hint}</div>
                          )}
                          {selectedConfirmCandidate.payloadPreview && (
                            <pre className="p-1.5 rounded border border-slate-700 bg-slate-950/70 text-[10px] leading-relaxed text-slate-300 whitespace-pre-wrap break-all">
                              {selectedConfirmCandidate.payloadPreview}
                            </pre>
                          )}
                        </div>
                      )}
                    </div>
                  ) : (
                    <div className="px-2 py-1.5 rounded border border-dashed border-slate-700 text-[11px] text-slate-500">
                      未从会话快照提取到候选确认项；可手工填写 function_call_id / invocation_id / ticket / nonce 后直接提交。
                    </div>
                  )}
                  <input
                    value={functionCallId}
                    onChange={(e) => setFunctionCallId(e.target.value)}
                    placeholder="function_call_id"
                    className="w-full px-2.5 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 font-mono"
                  />
                  <input
                    value={confirmHint}
                    onChange={(e) => setConfirmHint(e.target.value)}
                    placeholder="hint (可选)"
                    className="w-full px-2.5 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200"
                  />
                  <input
                    value={confirmInvocationId}
                    onChange={(e) => setConfirmInvocationId(e.target.value)}
                    placeholder="invocation_id (批准必填)"
                    className="w-full px-2.5 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 font-mono"
                  />
                  <input
                    value={confirmTicket}
                    onChange={(e) => setConfirmTicket(e.target.value)}
                    placeholder="confirmation_ticket"
                    className="w-full px-2.5 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 font-mono"
                  />
                  <input
                    value={confirmNonce}
                    onChange={(e) => setConfirmNonce(e.target.value)}
                    placeholder="nonce"
                    className="w-full px-2.5 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 font-mono"
                  />
                  <input
                    value={confirmNonceExpiresAt}
                    onChange={(e) => setConfirmNonceExpiresAt(e.target.value)}
                    placeholder="nonce_expires_at (ISO/ms)"
                    className="w-full px-2.5 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 font-mono"
                  />
                  <input
                    value={confirmTenantId}
                    onChange={(e) => setConfirmTenantId(e.target.value)}
                    placeholder="tenant_id (可选)"
                    className="w-full px-2.5 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 font-mono"
                  />
                  <textarea
                    value={confirmPayload}
                    onChange={(e) => setConfirmPayload(e.target.value)}
                    rows={3}
                    placeholder="payload JSON (可选)"
                    className="w-full px-2.5 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 font-mono"
                  />
                  {supportsExplicitReject ? (
                    <div className="grid grid-cols-2 gap-2 text-xs text-slate-300">
                      <label className="flex items-center gap-2 rounded border border-slate-700 px-2 py-1.5">
                        <input
                          type="radio"
                          name="confirm-action"
                          checked={!confirmed}
                          onChange={() => setConfirmed(false)}
                          className="accent-amber-500"
                        />
                        拒绝
                      </label>
                      <label className="flex items-center gap-2 rounded border border-slate-700 px-2 py-1.5">
                        <input
                          type="radio"
                          name="confirm-action"
                          checked={confirmed}
                          onChange={() => setConfirmed(true)}
                          className="accent-indigo-500"
                        />
                        批准
                      </label>
                    </div>
                  ) : (
                    <div className="px-2 py-1.5 rounded border border-slate-700 text-[11px] text-slate-300">
                      当前后端能力: 仅提交批准
                    </div>
                  )}
                  {approvalBlockedReason && (
                    <div className="px-2 py-1.5 rounded border border-red-500/30 bg-red-500/10 text-[11px] text-red-200">
                      {approvalBlockedReason}
                    </div>
                  )}
                  <button
                    type="button"
                    onClick={() => void handleConfirmTool()}
                    disabled={submitting || !selectedSessionId || !functionCallId.trim()}
                    className="w-full px-2.5 py-1.5 text-xs rounded border border-indigo-500/40 bg-indigo-500/15 text-indigo-200 hover:bg-indigo-500/25 disabled:opacity-50 inline-flex items-center justify-center gap-1"
                  >
                    {submitting ? <Loader2 size={12} className="animate-spin" /> : <Check size={12} />}
                    提交{effectiveConfirmed ? '批准' : '拒绝'}
                  </button>
                </div>
              </div>

              <div className="p-3 rounded border border-slate-800 bg-slate-900/40">
                <div className="text-xs text-slate-300 font-medium mb-2">会话回滚（rewind）</div>
                <div className="space-y-2">
                  <input
                    value={rewindInvocationId}
                    onChange={(e) => setRewindInvocationId(e.target.value)}
                    placeholder="rewind_before_invocation_id"
                    className="w-full px-2.5 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 font-mono"
                  />
                  <button
                    type="button"
                    onClick={() => void handleRewind()}
                    disabled={submitting || !selectedSessionId || !rewindInvocationId.trim()}
                    className="w-full px-2.5 py-1.5 text-xs rounded border border-amber-500/40 bg-amber-500/15 text-amber-200 hover:bg-amber-500/25 disabled:opacity-50 inline-flex items-center justify-center gap-1"
                  >
                    {submitting ? <Loader2 size={12} className="animate-spin" /> : <Undo2 size={12} />}
                    执行回滚
                  </button>
                </div>
              </div>
            </div>

            <AdkExportPanel
              issues={exportPrecheckIssues}
              emptyText="当前会话未发现导出 precheck 拒绝记录。"
            />

            <StageReplayPanel
              sessionId={selectedSessionId}
              sessionSnapshot={sessionSnapshot}
              onReplayCompleted={() => {
                void loadSessionSnapshot();
                void loadSessions();
              }}
            />

            <div className="p-3 rounded border border-slate-800 bg-slate-900/30">
              <div className="flex items-center justify-between mb-2">
                <div className="text-xs text-slate-300 font-medium">会话快照</div>
                <div className="text-[10px] text-slate-500 font-mono">{activeSession?.id || '-'}</div>
              </div>
              {loadingSnapshot ? (
                <div className="py-8 flex items-center justify-center text-slate-500">
                  <Loader2 size={16} className="animate-spin" />
                </div>
              ) : sessionSnapshot ? (
                <pre className="text-[11px] leading-relaxed text-slate-200 bg-slate-950/60 border border-slate-800 rounded p-3 overflow-auto max-h-[320px]">
                  {JSON.stringify(sessionSnapshot, null, 2)}
                </pre>
              ) : (
                <div className="text-xs text-slate-500 py-6">请选择会话查看详情</div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default AdkSessionPanel;
