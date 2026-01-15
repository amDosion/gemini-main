import { BaseHandler } from './BaseHandler';
import { ExecutionContext, HandlerResult } from './types';

export class DeepResearchHandler extends BaseHandler {
  protected async doExecute(context: ExecutionContext): Promise<HandlerResult> {
    const { text, attachments, currentModel, onStreamUpdate } = context;

    // 1. 如果有附件，先上传到 File Search Store
    let fileSearchStoreNames: string[] | undefined;
    
    if (attachments && attachments.length > 0) {
      onStreamUpdate?.({
        content: '📤 正在上传文档到研究存储...\n\n',
      });

      try {
        const uploadedStores: string[] = [];
        
        for (const attachment of attachments) {
          // 获取文件内容（可能是 URL 或 Blob）
          let fileBlob: Blob;
          
          if (attachment.url.startsWith('blob:')) {
            const response = await fetch(attachment.url);
            fileBlob = await response.blob();
          } else {
            // 如果是云存储 URL，需要先下载
            const response = await fetch(attachment.url);
            fileBlob = await response.blob();
          }
          
          // 上传到 File Search Store
          const formData = new FormData();
          formData.append('file', fileBlob, attachment.name || 'document');
          
          const uploadResponse = await fetch('/api/file-search/upload', {
            method: 'POST',
            credentials: 'include', // 使用 Cookie 认证
            body: formData
          });
          
          if (!uploadResponse.ok) {
            const errorText = await uploadResponse.text();
            throw new Error(`文件上传失败: ${errorText}`);
          }
          
          const uploadData = await uploadResponse.json();
          uploadedStores.push(uploadData.file_search_store_name);
          
          onStreamUpdate?.({
            content: `📤 已上传: ${attachment.name}\n\n`,
          });
        }
        
        // 去重
        fileSearchStoreNames = [...new Set(uploadedStores)];
        
        onStreamUpdate?.({
          content: `✅ 文档上传完成，开始深度研究...\n\n`,
        });
      } catch (error) {
        throw new Error(`文档上传失败: ${error instanceof Error ? error.message : String(error)}`);
      }
    }

    // 2. 启动流式研究任务
    // ✅ 获取 access_token 并添加到 Authorization header
    const token = localStorage.getItem('access_token');
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    };
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    
    // ✅ 从 options 中获取 Deep Research 配置，如果没有则使用默认值
    const thinkingSummaries = context.options?.deepResearchConfig?.thinkingSummaries || 'auto';
    const researchMode = context.options?.deepResearchConfig?.researchMode || 'vertex-ai';
    
    // ✅ 调试日志：确认 researchMode 值
    console.log('[DeepResearchHandler] researchMode:', researchMode);
    console.log('[DeepResearchHandler] context.options?.deepResearchConfig:', context.options?.deepResearchConfig);
    
    const startResponse = await fetch('/api/research/stream/start', {
      method: 'POST',
      headers,
      credentials: 'include', // 同时使用 Cookie 认证（向后兼容）
      body: JSON.stringify({
        prompt: text,
        agent: currentModel.id || 'deep-research-pro-preview-12-2025',
        background: true,
        stream: true,
        research_mode: researchMode,  // ✅ 传递工作模式（vertex-ai 或 gemini-api）
        agent_config: {
          type: 'deep-research',
          thinking_summaries: thinkingSummaries  // ✅ 使用用户配置的思考摘要模式
        },
        file_search_store_names: fileSearchStoreNames  // 传递文档存储名称
      }),
    });

    if (!startResponse.ok) {
      const errorText = await startResponse.text();
      throw new Error(`Failed to start research task: ${startResponse.statusText} - ${errorText}`);
    }

    const startData = await startResponse.json();
    const { interaction_id } = startData;

    if (!interaction_id) {
      throw new Error('Failed to start research task: No interaction_id received.');
    }

    // 通知 UI 研究已开始
    const startMessage = fileSearchStoreNames && fileSearchStoreNames.length > 0
      ? '🔍 Deep Research 已启动，正在分析您的文档和问题...\n\n'
      : '🔍 Deep Research 已启动，正在分析您的问题...\n\n';
    
    onStreamUpdate?.({
      content: startMessage,
    });

    // 2. 使用 EventSource 接收 SSE 流（带自动重连）
    return new Promise((resolve, reject) => {
      let accumulatedText = '';  // 最终答案文本
      let accumulatedThoughts = '';  // 思考过程文本
      let lastEventId: string | null = null;  // 用于断点续传
      let isComplete = false;
      let retryCount = 0;
      const MAX_RETRIES = 5;  // 最大重试次数
      const RETRY_DELAY = 2000;  // 重试延迟（毫秒）
      let lastGroundingMetadata: any = undefined;  // ✅ 累积 grounding metadata

      // 连接函数（支持重连）
      const connectSSE = () => {
        // 构造SSE URL（包含 last_event_id 用于断点续传）
        // 注意：EventSource 不支持自定义 headers，所以认证通过 Cookie 进行
        let sseUrl = `/api/research/stream/${interaction_id}`;
        if (lastEventId) {
          sseUrl += `?last_event_id=${lastEventId}`;
          console.log('[DeepResearchHandler] 🔄 重连SSE（断点续传）:', `...&last_event_id=${lastEventId.substring(0, 8)}...`);
        } else {
          console.log('[DeepResearchHandler] 连接SSE:', sseUrl);
        }

        // EventSource 会自动发送 Cookie（同源请求），后端从 Cookie 获取用户信息并从数据库获取 API Key
        const eventSource = new EventSource(sseUrl);

        // 添加详细的连接状态监控
        console.log('[DeepResearchHandler] EventSource readyState:', eventSource.readyState);

        eventSource.onopen = () => {
          console.log('[DeepResearchHandler] ✅ SSE连接已建立');
          retryCount = 0;  // 重置重试计数
        };

        eventSource.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            console.log('[DeepResearchHandler] 收到事件:', data.event_type);

            // 保存 event_id 用于断点续传
            if (data.event_id) {
              lastEventId = data.event_id;
            }

            if (data.event_type === 'content.delta') {
              if (data.delta?.type === 'text') {
                // 累积最终答案文本
                accumulatedText += data.delta.text;
                
                // 组装完整内容：思考过程（在 <thinking> 中）+ 最终答案
                const fullContent = accumulatedThoughts 
                  ? `<thinking>\n${accumulatedThoughts}\n</thinking>\n\n${accumulatedText}`
                  : accumulatedText;
                
                onStreamUpdate?.({
                  content: fullContent,
                  groundingMetadata: lastGroundingMetadata,  // ✅ 传递累积的 grounding metadata
                });
              } else if (data.delta?.type === 'thought_summary') {
                // 累积思考过程
                const thoughtText = data.delta.content?.text || '';
                
                // 添加到思考过程（保持增量添加）
                if (thoughtText) {
                  accumulatedThoughts += (accumulatedThoughts ? '\n\n' : '') + thoughtText;
                  
                  // 组装完整内容：思考过程（在未闭合的 <thinking> 中，表示还在思考）+ 最终答案
                  const fullContent = `<thinking>\n${accumulatedThoughts}\n${accumulatedText}`;
                  
                  onStreamUpdate?.({
                    content: fullContent,
                    groundingMetadata: lastGroundingMetadata,  // ✅ 传递累积的 grounding metadata
                  });
                }
              }
            } else if (data.event_type === 'tool.call') {
              // ✅ 处理 Browser 工具调用事件
              const toolCall = data.tool_call;
              const toolName = toolCall?.name || 'unknown';
              const toolArgs = toolCall?.args || {};
              
              console.log(`[DeepResearchHandler] 🔧 工具调用: ${toolName}`, toolArgs);
              
              // 显示工具调用信息（类似 ChatHandlerClass.ts）
              const toolCallText = `\n\n> **调用工具:** \`${toolName}\`\n> **参数:** \`${JSON.stringify(toolArgs)}\`\n\n`;
              accumulatedText += toolCallText;
              
              onStreamUpdate?.({
                content: accumulatedText,
                groundingMetadata: lastGroundingMetadata,
              });
            } else if (data.event_type === 'tool.result') {
              // ✅ 处理 Browser 工具结果事件
              const toolResult = data.tool_result;
              const toolName = toolResult?.tool || 'unknown';
              const result = toolResult?.result || '';
              
              console.log(`[DeepResearchHandler] ✅ 工具结果: ${toolName}`, result.substring(0, 200));
              
              // 显示工具结果（类似 ChatHandlerClass.ts）
              const resultPreview = result.length > 200 ? result.substring(0, 200) + '...' : result;
              const toolResultText = `\n\n> **工具结果** (\`${toolName}\`):\n> \`\`\`\n> ${resultPreview.split('\n').join('\n> ')}\n> \`\`\`\n\n`;
              accumulatedText += toolResultText;
              
              onStreamUpdate?.({
                content: accumulatedText,
                groundingMetadata: lastGroundingMetadata,
              });
            } else if (data.event_type === 'interaction.complete') {
              // 研究完成
              console.log('[DeepResearchHandler] ✅ 研究完成');
              
              // ✅ 提取 grounding metadata（如果存在）
              if (data.grounding_metadata) {
                lastGroundingMetadata = data.grounding_metadata;
                console.log('[DeepResearchHandler] 找到 grounding metadata:', lastGroundingMetadata);
              }
              
              isComplete = true;
              eventSource.close();
              
              // 组装最终内容：闭合 thinking 标签
              const finalContent = accumulatedThoughts 
                ? `<thinking>\n${accumulatedThoughts}\n</thinking>\n\n${accumulatedText || '研究已完成。'}`
                : (accumulatedText || '研究已完成。');
              
              resolve({
                content: finalContent,
                attachments: [],
                groundingMetadata: lastGroundingMetadata,  // ✅ 传递 grounding metadata
              });
            } else if (data.event_type === 'error') {
              // 服务端错误
              console.error('[DeepResearchHandler] ❌ 服务端错误:', data.error);
              isComplete = true;
              eventSource.close();

              // 如果已有部分结果，返回部分结果而不是错误
              if (accumulatedText || accumulatedThoughts) {
                const partialContent = accumulatedThoughts
                  ? `<thinking>\n${accumulatedThoughts}\n</thinking>\n\n${accumulatedText}\n\n⚠️ 研究过程中出现错误: ${data.error?.message || JSON.stringify(data.error)}`
                  : `${accumulatedText}\n\n⚠️ 研究过程中出现错误: ${data.error?.message || JSON.stringify(data.error)}`;
                
                resolve({
                  content: partialContent,
                  attachments: [],
                });
              } else {
                reject(new Error(data.error?.message || JSON.stringify(data.error) || 'Unknown error during research'));
              }
            }
          } catch (e) {
            console.error('[DeepResearchHandler] 解析 SSE 事件失败:', e, 'Raw data:', event.data);
          }
        };

        eventSource.onerror = (error) => {
          console.error('[DeepResearchHandler] ❌ SSE 连接错误:', error);
          console.error('[DeepResearchHandler] EventSource readyState:', eventSource.readyState);
          console.error('[DeepResearchHandler] EventSource url:', eventSource.url);

          // 尝试从event获取更多信息
          if (error instanceof Event) {
            console.error('[DeepResearchHandler] Error details:', {
              type: error.type,
              target: error.target,
              currentTarget: error.currentTarget,
              eventPhase: error.eventPhase,
              bubbles: error.bubbles,
              cancelable: error.cancelable,
              defaultPrevented: error.defaultPrevented,
              timeStamp: error.timeStamp
            });
          }

          eventSource.close();

          // 如果研究未完成且重试次数未用尽，则自动重连
          if (!isComplete && retryCount < MAX_RETRIES) {
            retryCount++;
            console.log(`[DeepResearchHandler] 🔄 尝试重连 (${retryCount}/${MAX_RETRIES})...`);

            // 显示重连提示（保持思考过程和答案的结构）
            const reconnectContent = accumulatedThoughts
              ? `<thinking>\n${accumulatedThoughts}\n${accumulatedText}\n\n🔄 连接中断，正在重连 (${retryCount}/${MAX_RETRIES})...`
              : `${accumulatedText}\n\n🔄 连接中断，正在重连 (${retryCount}/${MAX_RETRIES})...`;
            
            onStreamUpdate?.({
              content: reconnectContent,
            });

            setTimeout(() => {
              connectSSE();  // 重连
            }, RETRY_DELAY);
          } else if (!isComplete) {
            // 重试次数用尽
            console.error('[DeepResearchHandler] ❌ 重试次数用尽');

            if (accumulatedText || accumulatedThoughts) {
              const partialContent = accumulatedThoughts
                ? `<thinking>\n${accumulatedThoughts}\n</thinking>\n\n${accumulatedText}\n\n⚠️ 连接多次中断，以上为部分结果。`
                : `${accumulatedText}\n\n⚠️ 连接多次中断，以上为部分结果。`;
              
              resolve({
                content: partialContent,
                attachments: [],
              });
            } else {
              reject(new Error('SSE connection failed after retries'));
            }
          }
        };

        // 超时处理（10分钟 - 考虑到研究可能需要较长时间）
        setTimeout(() => {
          if (!isComplete && eventSource.readyState !== EventSource.CLOSED) {
            console.warn('[DeepResearchHandler] ⏱️ 研究超时');
            eventSource.close();
            
            if (accumulatedText || accumulatedThoughts) {
              const timeoutContent = accumulatedThoughts
                ? `<thinking>\n${accumulatedThoughts}\n</thinking>\n\n${accumulatedText}\n\n⏱️ 研究超时，以上为部分结果。`
                : `${accumulatedText}\n\n⏱️ 研究超时，以上为部分结果。`;
              
              resolve({
                content: timeoutContent,
                attachments: [],
              });
            } else {
              reject(new Error('Research timeout'));
            }
          }
        }, 600000);  // 10分钟超时
      };

      // 开始第一次连接
      connectSSE();
    });
  }
}
