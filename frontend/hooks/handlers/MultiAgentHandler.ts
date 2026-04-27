import { BaseHandler } from './BaseHandler';
import { ExecutionContext, HandlerResult } from './types';
import { requestJson } from '../../services/http';

interface AgentOutput {
  agentName?: string;
  text?: string;
  result?: { text?: string };
}

interface WorkflowResult {
  status?: string;
  error?: string;
  outputs?: Record<string, AgentOutput>;
  finalOutput?: { text?: string };
}

interface MultiAgentResponse {
  status?: string;
  error?: string;
  result?: WorkflowResult;
  data?: MultiAgentResponse;
}

interface WorkflowNode {
  id?: string;
  type?: string;
  data?: { type?: string; [k: string]: unknown };
  position?: { x: number; y: number };
  [k: string]: unknown;
}

interface WorkflowEdge {
  id?: string;
  source?: string;
  target?: string;
  sourceHandle?: string;
  targetHandle?: string;
}

interface WorkflowConfig {
  nodes?: WorkflowNode[];
  edges?: WorkflowEdge[];
}

export class MultiAgentHandler extends BaseHandler {
  protected async doExecute(context: ExecutionContext): Promise<HandlerResult> {
    const { text, attachments, currentModel, llmService, onStreamUpdate } = context;
    const workflowConfig = context.options?.multiAgentConfig;

    onStreamUpdate?.({
      content: '🔄 正在执行多智能体工作流...\n\n',
    });

    try {
      const providerId = String(llmService.getProviderId() || '').trim();
      if (!providerId) {
        throw new Error('当前 Multi-Agent 模式缺少 providerId');
      }

      const normalizedPrompt = text || '执行多智能体任务';
      const workflowPayload = this.buildWorkflowPayload(workflowConfig, normalizedPrompt);
      let displayText = '';
      const modeResponse = await requestJson<MultiAgentResponse>(
        `/api/modes/${encodeURIComponent(providerId)}/multi-agent`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          withAuth: true,
          timeoutMs: 0,
          errorMessage: '工作流执行失败',
          body: JSON.stringify({
            modelId: currentModel.id,
            prompt: normalizedPrompt,
            attachments,
            options: {},
            extra: workflowPayload
              ? {
                  workflow: workflowPayload,
                }
              : {
                  meta: { source: 'chat-handler' },
                },
          }),
        }
      );
      const result: MultiAgentResponse | WorkflowResult = (modeResponse?.data ??
        modeResponse) as MultiAgentResponse;
      if (result?.status && result.status !== 'completed') {
        throw new Error(result?.error || `工作流状态异常: ${result.status}`);
      }
      const workflow: WorkflowResult =
        (result as MultiAgentResponse)?.result ?? (result as WorkflowResult);
      displayText = this.formatWorkflowResult(workflow);

      onStreamUpdate?.({
        content: `✅ 工作流执行完成\n\n${displayText}`,
      });

      return {
        content: displayText,
        attachments: [],
      };
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      onStreamUpdate?.({ content: `❌ 工作流执行失败: ${errorMessage}` });
      throw error;
    }
  }

  private buildWorkflowPayload(
    workflowConfig: unknown,
    prompt: string
  ): Record<string, unknown> | null {
    const wf = (
      workflowConfig && typeof workflowConfig === 'object' ? workflowConfig : null
    ) as WorkflowConfig | null;
    if (!wf || !Array.isArray(wf.nodes) || wf.nodes.length === 0) {
      return null;
    }

    const normalizedNodes = wf.nodes
      .filter(
        (node): node is WorkflowNode =>
          !!node && typeof node === 'object' && !!String(node.id || '').trim()
      )
      .map((node) => {
        const normalizedType = String(node?.data?.type || node?.type || '').trim();
        return {
          ...node,
          type: normalizedType || node.type,
          data: {
            ...(node?.data || {}),
            type: normalizedType || node.type,
          },
          position: node?.position || { x: 0, y: 0 },
        };
      });

    if (normalizedNodes.length === 0) {
      return null;
    }

    const normalizedEdges = Array.isArray(wf.edges)
      ? wf.edges
          .filter((edge): edge is WorkflowEdge => !!edge && typeof edge === 'object')
          .map((edge) => ({
            id: edge.id,
            source: edge.source,
            target: edge.target,
            sourceHandle: edge.sourceHandle,
            targetHandle: edge.targetHandle,
          }))
      : [];

    return {
      nodes: normalizedNodes,
      edges: normalizedEdges,
      input: { task: prompt },
      meta: { source: 'chat-handler' },
      asyncMode: false,
    };
  }

  private formatWorkflowResult(result: WorkflowResult | undefined): string {
    if (!result) {
      return '工作流执行完成，但无返回结果。';
    }

    const outputs = result.outputs || {};
    const chunks: string[] = [];

    for (const output of Object.values(outputs)) {
      const agentName = output?.agentName;
      if (output?.text && agentName) {
        chunks.push(`### ${agentName}\n${output.text}`);
        continue;
      }
      if (output?.text) {
        chunks.push(`${output.text}`);
        continue;
      }
      if (output?.result?.text) {
        chunks.push(`${output.result.text}`);
      }
    }

    if (chunks.length > 0) {
      return chunks.join('\n\n');
    }

    const finalOutput = result.finalOutput;
    if (finalOutput?.text) {
      return finalOutput.text;
    }
    return JSON.stringify(result, null, 2);
  }
}
