import { BaseHandler } from './BaseHandler';
import { ExecutionContext, HandlerResult } from './types';

export class DeepResearchHandler extends BaseHandler {
  protected async doExecute(context: ExecutionContext): Promise<HandlerResult> {
    const { text, attachments, currentModel, onStreamUpdate, apiKey } = context;

    if (!apiKey) {
      throw new Error('API Key is required for Deep Research');
    }

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
            headers: {
              'Authorization': `Bearer ${apiKey}`
            },
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
    const startResponse = await fetch('/api/research/stream/start', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${apiKey}`
      },
      body: JSON.stringify({
        prompt: text,
        agent: currentModel.id || 'deep-research-pro-preview-12-2025',
        background: true,
        stream: true,
        agent_config: {
          type: 'deep-research',
          thinking_summaries: 'auto'  // 关键配置：启用思考摘要
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

      // 连接函数（支持重连）
      const connectSSE = () => {
        // 构造SSE URL（包含 last_event_id 用于断点续传）
        let sseUrl = `/api/research/stream/${interaction_id}?authorization=${encodeURIComponent(`Bearer ${apiKey}`)}`;
        if (lastEventId) {
          sseUrl += `&last_event_id=${lastEventId}`;
          console.log('[DeepResearchHandler] 🔄 重连SSE（断点续传）:', `...&last_event_id=${lastEventId.substring(0, 8)}...`);
        } else {
          console.log('[DeepResearchHandler] 连接SSE:', sseUrl.replace(apiKey, '***'));
        }

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
                  });
                }
              }
            } else if (data.event_type === 'interaction.complete') {
              // 研究完成
              console.log('[DeepResearchHandler] ✅ 研究完成');
              isComplete = true;
              eventSource.close();
              
              // 组装最终内容：闭合 thinking 标签
              const finalContent = accumulatedThoughts 
                ? `<thinking>\n${accumulatedThoughts}\n</thinking>\n\n${accumulatedText || '研究已完成。'}`
                : (accumulatedText || '研究已完成。');
              
              resolve({
                content: finalContent,
                attachments: [],
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
