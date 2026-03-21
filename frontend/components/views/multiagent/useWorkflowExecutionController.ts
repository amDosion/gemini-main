import { syncTokenToCookie } from '../../../services/authTokenStore';
import {
  useCallback,
  useEffect,
  useState,
  type Dispatch,
  type MutableRefObject,
  type SetStateAction,
} from 'react';
import { syncTokenToCookie } from '../../../services/authTokenStore';
import { getAccessToken } from '../../../services/apiClient';
import { syncTokenToCookie } from '../../../services/authTokenStore';
import { requestJson } from '../../../services/http';
import { syncTokenToCookie } from '../../../services/authTokenStore';
import {
  DEFAULT_WORKFLOW_EXECUTION_POLICY,
  fetchWorkflowExecutionPolicy,
  type WorkflowExecutionPolicy,
} from '../../../services/runtimePolicies';
import type { ExecutionStatus, WorkflowEdge, WorkflowNode } from '../../multiagent/types';
import { syncTokenToCookie } from '../../../services/authTokenStore';
import { useWorkflowExecutionStream } from './useWorkflowExecutionStream';
import { syncTokenToCookie } from '../../../services/authTokenStore';
import {
  buildFailedExecutionStatus,
  createInitialExecutionStatus,
} from './executionStatusUtils';
import { syncTokenToCookie } from '../../../services/authTokenStore';
import { isWorkflowExecutionAbortError } from './workflowExecutionErrors';

interface WorkflowExecuteRequest {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  prompt?: string;
  input?: Record<string, any>;
  meta?: {
    source?: 'editor' | 'template';
    templateId?: string;
    templateName?: string;
  };
}

interface UseWorkflowExecutionControllerParams {
  providerId?: string;
  modelId?: string;
  setExecutionStatus: Dispatch<SetStateAction<ExecutionStatus | undefined>>;
  showError: (message: string) => void;
  isMountedRef: MutableRefObject<boolean>;
  activeExecutionControllerRef: MutableRefObject<AbortController | null>;
  activeExecutionCleanupRef: MutableRefObject<(() => void) | null>;
  createRequestController: () => AbortController;
  releaseRequestController: (controller: AbortController) => void;
  fetchWorkflowHistory: () => Promise<void>;
}

const createExecutePayload = (workflow: WorkflowExecuteRequest, workflowPrompt: string) => {
  const nodesPayload = workflow.nodes.map((node) => {
    const normalizedType = String(node.data?.type || node.type || '').trim();
    return {
      id: node.id,
      type: normalizedType || node.type,
      data: {
        ...(node.data || {}),
        type: normalizedType || node.type,
      },
      position: node.position,
    };
  });

  const edgesPayload = workflow.edges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    sourceHandle: (edge as any).sourceHandle,
    targetHandle: (edge as any).targetHandle,
  }));

  const workflowInput =
    workflow.input && typeof workflow.input === 'object' && !Array.isArray(workflow.input)
      ? { ...workflow.input }
      : {};
  workflowInput.task = String(
    workflowInput.task || workflowInput.prompt || workflowInput.text || workflowPrompt
  ).trim() || workflowPrompt;

  const templateId = String(workflow?.meta?.templateId || '').trim();
  const templateName = String(workflow?.meta?.templateName || '').trim();
  const executionSource = templateId ? 'template' : 'editor';
  const requestMeta: Record<string, any> = {
    title: workflowPrompt ? workflowPrompt.slice(0, 80) : '工作流执行',
    source: executionSource,
  };

  if (templateId) {
    requestMeta.templateId = templateId;
  }

  if (templateName) {
    requestMeta.templateName = templateName;
  }

  return {
    nodes: nodesPayload,
    edges: edgesPayload,
    input: workflowInput,
    meta: requestMeta,
    asyncMode: true,
  };
};

export const useWorkflowExecutionController = ({
  providerId,
  modelId,
  setExecutionStatus,
  showError,
  isMountedRef,
  activeExecutionControllerRef,
  activeExecutionCleanupRef,
  createRequestController,
  releaseRequestController,
  fetchWorkflowHistory,
}: UseWorkflowExecutionControllerParams) => {
  const [workflowExecutionPolicy, setWorkflowExecutionPolicy] = useState<WorkflowExecutionPolicy>(
    DEFAULT_WORKFLOW_EXECUTION_POLICY
  );
  const { runWorkflowExecutionStream } = useWorkflowExecutionStream();

  useEffect(() => {
    let cancelled = false;

    const loadExecutionPolicy = async () => {
      const policy = await fetchWorkflowExecutionPolicy();
      if (!cancelled) {
        setWorkflowExecutionPolicy(policy);
      }
    };

    void loadExecutionPolicy();

    return () => {
      cancelled = true;
    };
  }, []);

  const handleWorkflowExecute = useCallback(
    async (workflow: WorkflowExecuteRequest) => {
      const previousExecutionController = activeExecutionControllerRef.current;
      if (previousExecutionController) {
        previousExecutionController.abort();
        releaseRequestController(previousExecutionController);
      }

      if (activeExecutionCleanupRef.current) {
        activeExecutionCleanupRef.current();
        activeExecutionCleanupRef.current = null;
      }

      const executionController = createRequestController();
      activeExecutionControllerRef.current = executionController;

      const shouldIgnoreStateUpdate = () =>
        !isMountedRef.current || executionController.signal.aborted;
      const workflowPrompt = workflow.prompt || '执行多智能体工作流';
      let terminalFailureMessage: string | null = null;
      const finalizeExecutionFailure = async (
        errorMessage: string,
        options: { skipStatusWrite?: boolean } = {}
      ) => {
        if (!options.skipStatusWrite) {
          setExecutionStatus((prev) =>
            prev ? buildFailedExecutionStatus(prev, errorMessage) : prev
          );
        }
        showError(`工作流执行失败: ${errorMessage}`);
        await fetchWorkflowHistory();
      };

      try {
        if (shouldIgnoreStateUpdate()) return;

        const initialStatus = createInitialExecutionStatus(workflow.nodes);
        setExecutionStatus({
          ...initialStatus,
          logs: [
            ...initialStatus.logs,
            {
              timestamp: Date.now(),
              nodeId: 'system',
              message: '工作流执行开始',
              level: 'info' as const,
            },
          ],
        });

        const token = getAccessToken();
        if (token) {
          syncTokenToCookie(token);
        }

        const normalizedProviderId = String(providerId || '').trim();
        if (!normalizedProviderId) {
          throw new Error('当前 Multi-Agent 模式缺少 providerId');
        }
        const normalizedModelId =
          String(modelId || '').trim() || 'workflow-runtime';

        const modeResponse = await requestJson<any>(`/api/modes/${encodeURIComponent(normalizedProviderId)}/multi-agent`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          withAuth: true,
          credentials: 'include',
          signal: executionController.signal,
          timeoutMs: 0,
          errorMessage: '工作流执行失败',
          body: JSON.stringify({
            modelId: normalizedModelId,
            prompt: workflowPrompt,
            attachments: [],
            options: {},
            extra: {
              workflow: createExecutePayload(workflow, workflowPrompt),
            },
          }),
        });
        const result = modeResponse?.data ?? modeResponse;

        if (shouldIgnoreStateUpdate()) return;


        const receivedExecutionId = result.executionId;
        if (receivedExecutionId) {
          setExecutionStatus((prev) =>
            prev
              ? {
                  ...prev,
                  executionId: receivedExecutionId,
                }
              : prev
          );
        }

        await runWorkflowExecutionStream({
          executeResult: result,
          executionId: receivedExecutionId,
          executionController,
          activeExecutionCleanupRef,
          setExecutionStatus,
          workflowExecutionPolicy,
          shouldIgnoreStateUpdate,
          onTerminalFailed: (errorMessage) => {
            terminalFailureMessage = errorMessage;
          },
        });

        if (!shouldIgnoreStateUpdate()) {
          await fetchWorkflowHistory();
        }
      } catch (error) {
        if (isWorkflowExecutionAbortError(error) || shouldIgnoreStateUpdate()) {
          return;
        }

        const errorMessage =
          terminalFailureMessage ||
          (error instanceof Error ? error.message : String(error));

        if (terminalFailureMessage) {
          await finalizeExecutionFailure(errorMessage, { skipStatusWrite: true });
          return;
        }

        await finalizeExecutionFailure(errorMessage);
      } finally {
        if (activeExecutionControllerRef.current === executionController) {
          if (activeExecutionCleanupRef.current) {
            activeExecutionCleanupRef.current();
            activeExecutionCleanupRef.current = null;
          }
          activeExecutionControllerRef.current = null;
        }

        releaseRequestController(executionController);
      }
    },
    [
      activeExecutionCleanupRef,
      activeExecutionControllerRef,
      createRequestController,
      fetchWorkflowHistory,
      isMountedRef,
      releaseRequestController,
      runWorkflowExecutionStream,
      setExecutionStatus,
      showError,
      providerId,
      modelId,
      workflowExecutionPolicy,
    ]
  );

  return {
    handleWorkflowExecute,
  };
};
