import { BaseHandler } from './BaseHandler';
import { ExecutionContext, HandlerResult } from './types';

export class MultiAgentHandler extends BaseHandler {
  protected async doExecute(context: ExecutionContext): Promise<HandlerResult> {
    const { text, onStreamUpdate } = context;

    // 从 options 中获取工作流配置
    const workflowConfig = context.options?.multiAgentConfig;
    
    if (!workflowConfig || !workflowConfig.nodes || workflowConfig.nodes.length === 0) {
      throw new Error('Multi-Agent 工作流配置无效：缺少节点');
    }

    onStreamUpdate?.({
      content: '🔄 正在执行多智能体工作流...\n\n',
    });

    try {
      const token = localStorage.getItem('access_token');
      const headers: HeadersInit = {
        'Content-Type': 'application/json',
      };
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      // 构建任务描述
      const taskDescription = text || workflowConfig.nodes
        .filter((n: any) => n.type === 'agent')
        .map((n: any) => `${n.label}(${n.agentId || 'default'})`)
        .join(' -> ');

      const agentIds = workflowConfig.nodes
        .filter((n: any) => n.type === 'agent' && n.agentId)
        .map((n: any) => n.agentId!)
        .filter(Boolean);

      const response = await fetch('/api/multi-agent/orchestrate', {
        method: 'POST',
        headers,
        credentials: 'include',
        body: JSON.stringify({
          task: taskDescription,
          agentIds: agentIds.length > 0 ? agentIds : undefined
        }),
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`工作流执行失败: ${errorText}`);
      }

      const result = await response.json();
      
      onStreamUpdate?.({
        content: `✅ 多智能体工作流执行完成\n\n结果：\n${JSON.stringify(result, null, 2)}`,
      });

      return {
        content: `多智能体工作流执行完成。\n\n任务：${taskDescription}\n\n结果：\n${JSON.stringify(result, null, 2)}`,
        attachments: [],
      };
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      onStreamUpdate?.({
        content: `❌ 工作流执行失败: ${errorMessage}`,
      });
      throw error;
    }
  }
}
