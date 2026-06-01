/**
 * useWorkflowExecuteHandler
 *
 * Extracts handleExecute (originally L1100-1378 of
 * MultiAgentWorkflowEditorReactFlow.tsx) into a dedicated hook that owns the
 * execution result state slice (isExecuting / executeErrorBanner /
 * finalResult / finalError / finalCompletedAt / finalRuntime /
 * finalRuntimeHints) and exposes the bound callback along with their setters.
 *
 * Behaviour is preserved 1:1 — every validation branch, fallback prompt
 * parsing path, image/file pickling rule and addLog call mirrors the
 * original implementation.
 */

import { useCallback, useState } from 'react';
import type { Edge, Node } from 'reactflow';

import type { WorkflowEdge, WorkflowNode, WorkflowNodeData } from '../types';
import type { ActiveTemplateMeta } from '../workflowTemplateLoader';
import { formatWorkflowValidationError, validateWorkflow } from '../workflowUtils';
import { buildWorkflowStructureFingerprint } from '../workflowEditorUtils';
import { hasUsableImageInput } from '../workflowResultUtils';
import { mergeUniqueStringList, normalizeStringList } from '../workflowGraphUtils';
import { classifyToolNode } from '../toolClassification';
import { normalizeWorkflowAgentTaskType } from '../workflowContract';
import { getErrorMessage } from '../../../utils/errorMessage';

import type { LogLevel } from '../ExecutionLogPanel';

type AddLog = (
  nodeId: string,
  nodeName: string,
  level: LogLevel,
  message: string,
  timestamp?: number
) => void;

export interface UseWorkflowExecuteHandlerArgs {
  onExecute?: (workflow: {
    nodes: WorkflowNode[];
    edges: WorkflowEdge[];
    prompt: string;
    input?: Record<string, any>;
    meta?: {
      source: 'editor' | 'template';
      templateId?: string;
      templateName?: string;
    };
  }) => void | Promise<void>;
  nodes: Node<WorkflowNodeData>[];
  edges: Edge[];
  workflowPrompt: string;
  workflowInputImageUrl: string;
  workflowInputFileUrl: string;
  activeTemplateMeta: ActiveTemplateMeta | null;
  activeTemplateFingerprint: string | null;
  addLog: AddLog;
  setShowLogs: (value: boolean) => void;
}

export interface UseWorkflowExecuteHandlerResult {
  handleExecute: () => Promise<void>;
  isExecuting: boolean;
  executeErrorBanner: string | null;
  setExecuteErrorBanner: React.Dispatch<React.SetStateAction<string | null>>;
  finalResult: any;
  setFinalResult: React.Dispatch<React.SetStateAction<any>>;
  finalError: string | null;
  setFinalError: React.Dispatch<React.SetStateAction<string | null>>;
  finalCompletedAt: number | null;
  setFinalCompletedAt: React.Dispatch<React.SetStateAction<number | null>>;
  finalRuntime: string;
  setFinalRuntime: React.Dispatch<React.SetStateAction<string>>;
  finalRuntimeHints: string[];
  setFinalRuntimeHints: React.Dispatch<React.SetStateAction<string[]>>;
}

export const useWorkflowExecuteHandler = ({
  onExecute,
  nodes,
  edges,
  workflowPrompt,
  workflowInputImageUrl,
  workflowInputFileUrl,
  activeTemplateMeta,
  activeTemplateFingerprint,
  addLog,
  setShowLogs,
}: UseWorkflowExecuteHandlerArgs): UseWorkflowExecuteHandlerResult => {
  const [isExecuting, setIsExecuting] = useState(false);
  const [executeErrorBanner, setExecuteErrorBanner] = useState<string | null>(null);
  const [finalResult, setFinalResult] = useState<any>(null);
  const [finalError, setFinalError] = useState<string | null>(null);
  const [finalCompletedAt, setFinalCompletedAt] = useState<number | null>(null);
  const [finalRuntime, setFinalRuntime] = useState<string>('');
  const [finalRuntimeHints, setFinalRuntimeHints] = useState<string[]>([]);

  const handleExecute = useCallback(async () => {
    if (!onExecute) {
      const message = '未配置执行处理器，无法启动工作流';
      addLog('system', '系统', 'warn', message);
      setExecuteErrorBanner(message);
      setShowLogs(true);
      return;
    }
    if (isExecuting) {
      const message = '工作流正在执行中，请稍候';
      addLog('system', '系统', 'warn', message);
      setExecuteErrorBanner(message);
      return;
    }

    try {
      setExecuteErrorBanner(null);
      const validation = validateWorkflow(nodes as Node<WorkflowNodeData>[], edges as Edge[]);
      if (!validation.isValid) {
        throw new Error(formatWorkflowValidationError(validation));
      }

      setIsExecuting(true);
      addLog('system', '系统', 'info', '开始执行工作流...');
      const pickFirstNodeValue = (candidateTypes: string[], key: keyof WorkflowNodeData) => {
        for (const node of nodes as WorkflowNode[]) {
          const nodeType = String(node?.data?.type || node?.type || '').toLowerCase();
          if (!candidateTypes.includes(nodeType)) {
            continue;
          }
          const value = node?.data?.[key];
          const text = typeof value === 'string' ? value.trim() : '';
          if (text) {
            return text;
          }
        }
        return '';
      };
      const pickFirstNodeList = (
        candidateTypes: string[],
        listKey: keyof WorkflowNodeData,
        singleKey: keyof WorkflowNodeData
      ): string[] => {
        for (const node of nodes as WorkflowNode[]) {
          const nodeType = String(node?.data?.type || node?.type || '').toLowerCase();
          if (!candidateTypes.includes(nodeType)) {
            continue;
          }
          const listValue = mergeUniqueStringList(
            normalizeStringList(node?.data?.[listKey]),
            typeof node?.data?.[singleKey] === 'string'
              ? [String(node.data[singleKey] || '').trim()]
              : []
          );
          if (listValue.length > 0) {
            return listValue;
          }
        }
        return [];
      };

      const startNode = (nodes as WorkflowNode[]).find((node) => {
        const nodeType = (node?.data?.type || node?.type || '').toLowerCase();
        return nodeType === 'start';
      });
      const startTask = String(startNode?.data?.startTask || '').trim();
      const startImageInputs = mergeUniqueStringList(
        normalizeStringList(startNode?.data?.startImageUrls),
        startNode?.data?.startImageUrl ? [String(startNode.data.startImageUrl).trim()] : []
      );
      const startFileInputs = mergeUniqueStringList(
        normalizeStringList(startNode?.data?.startFileUrls),
        startNode?.data?.startFileUrl ? [String(startNode.data.startFileUrl).trim()] : []
      );
      const inputTextNodeTask = pickFirstNodeValue(['input_text'], 'startTask');
      const inputImageNodeUrls = pickFirstNodeList(
        ['input_image'],
        'startImageUrls',
        'startImageUrl'
      );
      const inputFileNodeUrls = pickFirstNodeList(['input_file'], 'startFileUrls', 'startFileUrl');

      const effectivePrompt = String(startTask || inputTextNodeTask || workflowPrompt || '').trim();
      const rawPrompt = effectivePrompt;
      let workflowInput: Record<string, any> = { task: effectivePrompt };
      if (rawPrompt.startsWith('{') && rawPrompt.endsWith('}')) {
        try {
          const parsed = JSON.parse(rawPrompt);
          if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
            workflowInput = {
              ...parsed,
              task: parsed.task || parsed.prompt || parsed.text || effectivePrompt,
            };
          }
        } catch {
          // ignore invalid json prompt and use plain text input
        }
      }

      const promptImageInputs = mergeUniqueStringList(
        normalizeStringList(workflowInput.imageUrls),
        normalizeStringList((workflowInput as any).image_urls),
        typeof workflowInput.imageUrl === 'string' ? [workflowInput.imageUrl.trim()] : []
      );
      const preferredImageInputs =
        inputImageNodeUrls.length > 0
          ? inputImageNodeUrls
          : startImageInputs.length > 0
            ? startImageInputs
            : promptImageInputs.length > 0
              ? promptImageInputs
              : workflowInputImageUrl.trim()
                ? [workflowInputImageUrl.trim()]
                : [];
      const usableImageInputs = preferredImageInputs.filter((value) => hasUsableImageInput(value));
      if (usableImageInputs.length > 0) {
        workflowInput.imageUrl = usableImageInputs[0];
        workflowInput.imageUrls = usableImageInputs;
      } else {
        delete workflowInput.imageUrl;
        delete workflowInput.imageUrls;
      }

      const isUsableFileInput = (value: string) => {
        const normalized = String(value || '').trim();
        if (!normalized) return false;
        if (normalized.includes('{{') || normalized.includes('}}')) return false;
        return true;
      };
      const promptFileInputs = mergeUniqueStringList(
        normalizeStringList(workflowInput.fileUrls),
        normalizeStringList((workflowInput as any).file_urls),
        typeof workflowInput.fileUrl === 'string' ? [workflowInput.fileUrl.trim()] : []
      );
      const preferredFileInputs =
        inputFileNodeUrls.length > 0
          ? inputFileNodeUrls
          : startFileInputs.length > 0
            ? startFileInputs
            : promptFileInputs.length > 0
              ? promptFileInputs
              : workflowInputFileUrl.trim()
                ? [workflowInputFileUrl.trim()]
                : [];
      const usableFileInputs = preferredFileInputs.filter(isUsableFileInput);
      if (usableFileInputs.length > 0) {
        workflowInput.fileUrl = usableFileInputs[0];
        workflowInput.fileUrls = usableFileInputs;
      } else {
        delete workflowInput.fileUrl;
        delete workflowInput.fileUrls;
      }

      const hasGlobalImageInput =
        Array.isArray(workflowInput.imageUrls) && workflowInput.imageUrls.length > 0;
      const hasInvalidAgentImageTask = (nodes as WorkflowNode[]).some((node) => {
        const nodeType = (node?.data?.type || node?.type || '').toLowerCase();
        if (nodeType !== 'agent') return false;
        const hasNodeImage = Boolean(String(node?.data?.agentReferenceImageUrl || '').trim());
        if (!hasNodeImage) return false;
        const explicitTaskType = String(node?.data?.agentTaskType || '').trim();
        if (!explicitTaskType) return false;
        const taskType = normalizeWorkflowAgentTaskType(explicitTaskType, null);
        return !(
          taskType === 'vision-understand' ||
          taskType === 'image-edit' ||
          taskType === 'video-gen'
        );
      });
      if (hasInvalidAgentImageTask) {
        throw new Error(
          '存在智能体节点已配置参考图，但任务类型不是 vision-understand、image-edit 或 video-gen。请先修正节点配置。'
        );
      }
      const requiresImageInput = (nodes as WorkflowNode[]).some((node) => {
        const nodeType = (node?.data?.type || node?.type || '').toLowerCase();
        if (nodeType === 'agent') {
          const taskType = normalizeWorkflowAgentTaskType(node?.data?.agentTaskType, null);
          if (
            taskType === 'image-edit' ||
            taskType === 'vision-understand'
          ) {
            const hasNodeImage = Boolean(String(node?.data?.agentReferenceImageUrl || '').trim());
            return !hasNodeImage;
          }
        }
        if (nodeType === 'tool') {
          if (classifyToolNode(String(node?.data?.toolName || '')).isImageEdit) {
            const hasNodeImage = Boolean(String(node?.data?.toolReferenceImageUrl || '').trim());
            return !hasNodeImage;
          }
        }
        return false;
      });
      if (requiresImageInput && !hasGlobalImageInput) {
        throw new Error(
          '当前工作流包含图像编辑节点，请提供有效参考图片（上传图片或填写真实 input.imageUrl）'
        );
      }

      const currentFingerprint = buildWorkflowStructureFingerprint(
        nodes as Node<WorkflowNodeData>[],
        edges as Edge[]
      );
      const canSyncTemplateResult = Boolean(
        activeTemplateMeta?.templateId &&
        activeTemplateFingerprint &&
        activeTemplateFingerprint === currentFingerprint
      );

      await onExecute({
        nodes: nodes as WorkflowNode[],
        edges: edges as WorkflowEdge[],
        prompt: effectivePrompt,
        input: workflowInput,
        meta: canSyncTemplateResult
          ? {
              source: 'template',
              templateId: activeTemplateMeta?.templateId,
              templateName: activeTemplateMeta?.templateName || '',
            }
          : { source: 'editor' },
      });
      setExecuteErrorBanner(null);
      addLog('system', '系统', 'info', '工作流执行完成');
    } catch (error) {
      const errorMessage = getErrorMessage(error);
      setExecuteErrorBanner(errorMessage);
      setShowLogs(true);
      addLog('system', '系统', 'error', `工作流执行失败: ${errorMessage}`);
    } finally {
      setIsExecuting(false);
    }
  }, [
    addLog,
    onExecute,
    nodes,
    edges,
    workflowPrompt,
    workflowInputImageUrl,
    workflowInputFileUrl,
    activeTemplateMeta,
    activeTemplateFingerprint,
    isExecuting,
    setShowLogs,
  ]);

  return {
    handleExecute,
    isExecuting,
    executeErrorBanner,
    setExecuteErrorBanner,
    finalResult,
    setFinalResult,
    finalError,
    setFinalError,
    finalCompletedAt,
    setFinalCompletedAt,
    finalRuntime,
    setFinalRuntime,
    finalRuntimeHints,
    setFinalRuntimeHints,
  };
};
