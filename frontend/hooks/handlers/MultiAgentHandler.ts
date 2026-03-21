import { BaseHandler } from './BaseHandler';
import { ExecutionContext, HandlerResult } from './types';
import { requestJson } from '../../services/http';

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
      const modeResponse = await requestJson<any>(
        `/api/modes/${encodeURIComponent(providerId)}/multi-agent`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          withAuth: true,
          credentials: 'include',
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
      const result = modeResponse?.data ?? modeResponse;
      if (result?.status && result.status !== 'completed') {
        throw new Error(result?.error || `工作流状态异常: ${result.status}`);
      }
      displayText = this.formatWorkflowResult(result?.result ?? result);

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

  private buildWorkflowPayload(workflowConfig: any, prompt: string): Record<string, any> | null {
    if (!workflowConfig || !Array.isArray(workflowConfig.nodes) || workflowConfig.nodes.length === 0) {
      return null;
    }

    const normalizedNodes = workflowConfig.nodes
      .filter((node: any) => node && typeof node === 'object' && String(node.id || '').trim())
      .map((node: any) => {
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

    const normalizedEdges = Array.isArray(workflowConfig.edges)
      ? workflowConfig.edges
          .filter((edge: any) => edge && typeof edge === 'object')
          .map((edge: any) => ({
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

  private formatWorkflowResult(result: any): string {
    if (!result) {
      return '工作流执行完成，但无返回结果。';
    }

    const outputs = result?.outputs || {};
    const chunks: string[] = [];

    for (const output of Object.values(outputs)) {
      const out = output as any;
      const agentName = out?.agentName;
      if (out?.text && agentName) {
        chunks.push(`### ${agentName}\n${out.text}`);
        continue;
      }
      if (out?.text) {
        chunks.push(`${out.text}`);
        continue;
      }
      if (out?.result?.text) {
        chunks.push(`${out.result.text}`);
      }
    }

    if (chunks.length > 0) {
      return chunks.join('\n\n');
    }

    const finalOutput = result?.finalOutput;
    if (finalOutput?.text) {
      return finalOutput.text;
    }
    return JSON.stringify(result, null, 2);
  }
}
