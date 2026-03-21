import { useCallback, type Dispatch, type MutableRefObject, type SetStateAction } from 'react';
import type { ExecutionStatus } from '../../multiagent/types';
import { fetchWorkflowExecutionState } from '../../../services/workflowStateService';
import type { WorkflowExecutionPolicy } from '../../../services/runtimePolicies';
import {
  consumeExecutionStatePayload,
  executionStreamReducer,
  resolveConsumedStateFinalizePlan,
  resolveTerminalState,
  type ConsumedExecutionState,
  type ExecutionStreamAction,
} from './executionStreamReducer';
import {
  WORKFLOW_EXECUTION_ABORT_MESSAGE,
  isWorkflowExecutionAbortError,
} from './workflowExecutionErrors';

const WORKFLOW_POLLING_ERROR_BUDGET = 3;

type ExecutionStatusSetter = Dispatch<SetStateAction<ExecutionStatus | undefined>>;
type ExecutionLogLevel = ExecutionStatus['logs'][number]['level'];

interface RunWorkflowExecutionStreamParams {
  executeResult: unknown;
  executionId?: string;
  executionController: AbortController;
  activeExecutionCleanupRef: MutableRefObject<(() => void) | null>;
  setExecutionStatus: ExecutionStatusSetter;
  workflowExecutionPolicy: WorkflowExecutionPolicy;
  shouldIgnoreStateUpdate: () => boolean;
  onTerminalFailed: (errorMessage: string) => void;
}

const parseSseEventData = (event: Event): unknown => {
  if (!(event instanceof MessageEvent)) {
    return null;
  }
  try {
    const rawData =
      typeof event.data === 'string' ? event.data : JSON.stringify(event.data ?? null);
    return JSON.parse(rawData);
  } catch {
    return null;
  }
};

export const useWorkflowExecutionStream = () => {
  const runWorkflowExecutionStream = useCallback(
    async ({
      executeResult,
      executionId,
      executionController,
      activeExecutionCleanupRef,
      setExecutionStatus,
      workflowExecutionPolicy,
      shouldIgnoreStateUpdate,
      onTerminalFailed,
    }: RunWorkflowExecutionStreamParams): Promise<void> => {
      const dispatchStatusAction = (action: ExecutionStreamAction) => {
        if (shouldIgnoreStateUpdate()) return;
        setExecutionStatus((prev) => executionStreamReducer(prev, action));
      };

      const appendSystemLog = (message: string, level: ExecutionLogLevel) => {
        dispatchStatusAction({
          type: 'append_log',
          entry: {
            timestamp: Date.now(),
            nodeId: 'system',
            message,
            level,
          },
        });
      };

      const applySnapshot = (snapshot: unknown) => {
        dispatchStatusAction({ type: 'apply_snapshot', snapshot });
      };

      const applyCompletedState = (payload: unknown) => {
        dispatchStatusAction({
          type: 'apply_completed',
          payload,
          now: Date.now(),
        });
      };

      const applyTerminalState = (payload: unknown) => {
        const resolution = resolveTerminalState(payload);
        dispatchStatusAction({
          type: 'apply_terminal',
          resolution,
          now: Date.now(),
        });
        return {
          terminalStatus: resolution.terminalStatus,
          terminalError: resolution.terminalError,
        };
      };

      const consumeExecutionState = (payload: unknown): ConsumedExecutionState => {
        if (shouldIgnoreStateUpdate()) {
          return { consumed: false, normalizedPayload: null, status: 'pending' };
        }
        const consumedState = consumeExecutionStatePayload(payload);
        if (consumedState.consumed && consumedState.normalizedPayload) {
          applySnapshot(consumedState.normalizedPayload);
        }
        return consumedState;
      };

      const initialConsumedState = consumeExecutionState(executeResult);
      const initialFinalizePlan = resolveConsumedStateFinalizePlan(initialConsumedState, Date.now());
      if (initialFinalizePlan.kind === 'completed') {
        applyCompletedState(initialFinalizePlan.payload);
        return;
      }
      if (initialFinalizePlan.kind === 'terminal') {
        const { terminalStatus, terminalError } = applyTerminalState(initialFinalizePlan.payload);
        if (terminalStatus === 'failed') {
          onTerminalFailed(terminalError);
          throw new Error(terminalError);
        }
        return;
      }

      const safeExecutionId = String(executionId || '').trim();
      if (!safeExecutionId) {
        throw new Error('未获取到 executionId');
      }

      appendSystemLog('已提交执行任务，正在连接状态流...', 'info');

      await new Promise<void>((resolve, reject) => {
        const eventSource = new EventSource(`/api/workflows/${safeExecutionId}/status`);
        let finished = false;
        let lastEventAt = Date.now();
        let pollingTimer: number | undefined;
        let hardTimeoutTimer: number | undefined;
        let pollingErrorStreak = 0;
        const isAbortLikeError = (error: unknown) =>
          isWorkflowExecutionAbortError(error) ||
          executionController.signal.aborted ||
          finished;

        const markEvent = () => {
          lastEventAt = Date.now();
        };

        const handleAbort = () => {
          if (finished) return;
          finished = true;
          cleanup();
          reject(new Error(WORKFLOW_EXECUTION_ABORT_MESSAGE));
        };

        const cleanup = () => {
          eventSource.close();
          if (pollingTimer !== undefined) {
            window.clearInterval(pollingTimer);
          }
          if (hardTimeoutTimer !== undefined) {
            window.clearTimeout(hardTimeoutTimer);
          }
          executionController.signal.removeEventListener('abort', handleAbort);
          if (activeExecutionCleanupRef.current === cleanup) {
            activeExecutionCleanupRef.current = null;
          }
        };
        activeExecutionCleanupRef.current = cleanup;
        executionController.signal.addEventListener('abort', handleAbort, { once: true });

        const finalizeSuccess = (payload: unknown) => {
          if (finished) return;
          finished = true;
          markEvent();
          const consumedState = consumeExecutionState(payload);
          if (consumedState.consumed && consumedState.normalizedPayload) {
            applyCompletedState(consumedState.normalizedPayload);
          } else {
            applySnapshot(payload);
            applyCompletedState(payload);
          }
          cleanup();
          resolve();
        };

        const finalizeTerminal = (payload: unknown) => {
          if (finished) return;
          finished = true;
          markEvent();
          const consumedState = consumeExecutionState(payload);
          const terminalPayload =
            consumedState.consumed && consumedState.normalizedPayload
              ? consumedState.normalizedPayload
              : payload;
          if (!consumedState.consumed) {
            applySnapshot(terminalPayload);
          }
          const { terminalStatus, terminalError } = applyTerminalState(terminalPayload);
          cleanup();
          if (terminalStatus === 'failed') {
            onTerminalFailed(terminalError);
            reject(new Error(terminalError));
            return;
          }
          resolve();
        };

        const finalizeFromConsumedState = (
          consumedState: ConsumedExecutionState,
          options: {
            failedError?: string;
            pausedError?: string;
          } = {}
        ): boolean => {
          const finalizePlan = resolveConsumedStateFinalizePlan(consumedState, Date.now(), options);
          if (finalizePlan.kind === 'completed') {
            finalizeSuccess(finalizePlan.payload);
            return true;
          }
          if (finalizePlan.kind === 'terminal') {
            finalizeTerminal(finalizePlan.payload);
            return true;
          }
          return false;
        };

        pollingTimer = window.setInterval(async () => {
          if (finished || executionController.signal.aborted) return;
          if (Date.now() - lastEventAt < workflowExecutionPolicy.sseIdleThresholdMs) return;
          try {
            const pollPayload = await fetchWorkflowExecutionState(
              safeExecutionId,
              executionController.signal
            );
            if (finished || executionController.signal.aborted) return;
            if (pollingErrorStreak > 0) {
              appendSystemLog('轮询连接已恢复', 'info');
            }
            pollingErrorStreak = 0;
            const consumedPollState = consumeExecutionState(pollPayload);
            finalizeFromConsumedState(consumedPollState);
          } catch (pollError) {
            if (isAbortLikeError(pollError)) {
              return;
            }
            pollingErrorStreak += 1;
            appendSystemLog(
              `轮询状态失败（${pollingErrorStreak}/${WORKFLOW_POLLING_ERROR_BUDGET}）`,
              'warn'
            );
            if (pollingErrorStreak >= WORKFLOW_POLLING_ERROR_BUDGET) {
              finalizeTerminal({
                status: 'failed',
                error: `轮询状态连续失败 ${pollingErrorStreak} 次，已停止等待实时状态。请检查网络后重试，或稍后在历史记录中确认执行结果。`,
                completedAt: Date.now(),
              });
            }
          }
        }, workflowExecutionPolicy.pollingIntervalMs);

        hardTimeoutTimer = window.setTimeout(() => {
          if (finished || executionController.signal.aborted) return;
          const timeoutMinutes = Math.max(1, Math.round(workflowExecutionPolicy.hardTimeoutMs / 60_000));
          const timeoutMessage = `执行超时（${timeoutMinutes}分钟），已停止实时等待并标记为已暂停；请在工作流历史中查看后续状态。`;
          void (async () => {
            try {
              const timeoutPayload = await fetchWorkflowExecutionState(
                safeExecutionId,
                executionController.signal
              );
              if (finished || executionController.signal.aborted) return;
              const consumedTimeoutState = consumeExecutionState(timeoutPayload);
              if (finalizeFromConsumedState(consumedTimeoutState, { pausedError: timeoutMessage })) {
                return;
              }
            } catch (timeoutError) {
              if (isAbortLikeError(timeoutError)) {
                return;
              }
            }
            finalizeTerminal({
              status: 'workflow_paused',
              error: timeoutMessage,
              completedAt: Date.now(),
            });
          })();
        }, workflowExecutionPolicy.hardTimeoutMs);

        eventSource.addEventListener('execution_state', (event) => {
          const payload = parseSseEventData(event);
          if (!payload) return;
          markEvent();
          const consumedState = consumeExecutionState(payload);
          if (!consumedState.consumed) return;
          finalizeFromConsumedState(consumedState);
        });

        eventSource.onerror = () => {
          if (finished) return;
          markEvent();
          eventSource.close();
          appendSystemLog('状态流连接中断，已切换到轮询兜底...', 'warn');
        };
      });
    },
    []
  );

  return { runWorkflowExecutionStream };
};
