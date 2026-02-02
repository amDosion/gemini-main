import React, { useState, useCallback, useRef, lazy, Suspense } from 'react';
import MessageItem from '../chat/MessageItem';
import { Message, ModelConfig, AppMode, ChatOptions, Attachment, Role } from '../../types/types';
import type { WorkflowNode, WorkflowEdge, ExecutionStatus } from '../multiagent/types';
import { GenViewLayout } from '../common/GenViewLayout';
import { X, Network, MessageSquare, SlidersHorizontal, RotateCcw, Send, Paperclip, FileText } from 'lucide-react';
import { useToastContext } from '../../contexts/ToastContext';
import { LoadingSpinner } from '../common/LoadingSpinner';

// ✅ 懒加载 MultiAgentWorkflowEditor 组件
const MultiAgentWorkflowEditor = lazy(() => 
  import('../multiagent').then(m => ({ default: m.MultiAgentWorkflowEditorReactFlow }))
);

interface MultiAgentViewProps {
    messages: Message[];
    isLoadingModels: boolean;
    visibleModels: ModelConfig[];
    allVisibleModels?: ModelConfig[];  // ✅ 新增：完整模型列表
    apiKey: string;
    protocol: string;
    onPromptSelect: (text: string, mode: AppMode, modelId: string, requiredCap: string) => void;
    onOpenSettings: () => void;
    onImageClick: (url: string) => void;
    onEditImage: (url: string) => void;
    loadingState: string;
    onSend: (text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => void;
    onStop: () => void;
    activeModelConfig?: ModelConfig;
    appMode: AppMode;
    setAppMode: (mode: AppMode) => void;
    providerId?: string;
}

export const MultiAgentView: React.FC<MultiAgentViewProps> = React.memo(({
    messages,
    isLoadingModels,
    visibleModels,
    allVisibleModels = [],
    apiKey,
    protocol,
    onPromptSelect,
    onOpenSettings,
    onImageClick,
    onEditImage,
    loadingState,
    onSend,
    onStop,
    activeModelConfig,
    appMode,
    setAppMode,
    providerId
}) => {
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    
    // ✅ Multi-Agent 工作流执行状态
    const [executionStatus, setExecutionStatus] = useState<ExecutionStatus | undefined>(undefined);
    const [isMobileHistoryOpen, setIsMobileHistoryOpen] = useState(false);
    const [viewMode, setViewMode] = useState<'editor' | 'chat'>('editor');
    const { showError } = useToastContext();
    
    // ✅ 参数面板状态
    const [prompt, setPrompt] = useState('');
    const [activeAttachments, setActiveAttachments] = useState<Attachment[]>([]);

    // ✅ Multi-Agent 工作流执行处理
    const handleWorkflowExecute = useCallback(async (workflow: { nodes: WorkflowNode[]; edges: WorkflowEdge[] }) => {
        try {
            // 初始化执行状态
            const initialStatus: typeof executionStatus = {
                nodeStatuses: {},
                nodeProgress: {},
                nodeResults: {},
                nodeErrors: {},
                logs: []
            };
            
            workflow.nodes.forEach(node => {
                initialStatus.nodeStatuses[node.id] = 'pending';
                initialStatus.nodeProgress[node.id] = 0;
            });
            
            setExecutionStatus(initialStatus);
            
            // 添加开始日志
            setExecutionStatus(prev => ({
                ...prev!,
                logs: [...(prev?.logs || []), {
                    timestamp: Date.now(),
                    nodeId: 'system',
                    message: '工作流执行开始',
                    level: 'info' as const
                }]
            }));

            const token = localStorage.getItem('access_token');
            const headers: HeadersInit = {
                'Content-Type': 'application/json',
            };
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }

            // 构建任务描述（从工作流节点生成）
            const taskDescription = workflow.nodes
                .filter(n => n.type === 'agent')
                .map(n => `${n.data.label}(${n.data.agentId || 'default'})`)
                .join(' -> ');

            const agentIds = workflow.nodes
                .filter(n => n.type === 'agent' && n.data.agentId)
                .map(n => n.data.agentId!)
                .filter(Boolean);

            // 更新节点状态为运行中
            workflow.nodes.forEach(node => {
                setExecutionStatus(prev => ({
                    ...prev!,
                    nodeStatuses: { ...prev!.nodeStatuses, [node.id]: 'running' },
                    nodeProgress: { ...prev!.nodeProgress, [node.id]: 0 },
                    logs: [...(prev?.logs || []), {
                        timestamp: Date.now(),
                        nodeId: node.id,
                        message: `节点 ${node.data.label} 开始执行`,
                        level: 'info' as const
                    }]
                }));
            });

            const response = await fetch('/api/multi-agent/orchestrate', {
                method: 'POST',
                headers,
                credentials: 'include',
                body: JSON.stringify({
                    task: taskDescription || '执行多智能体工作流',
                    agentIds: agentIds.length > 0 ? agentIds : undefined
                }),
            });

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`工作流执行失败: ${errorText}`);
            }

            const result = await response.json();
            console.log('[MultiAgent] 工作流执行结果:', result);

            // 更新执行状态
            if (result.results && Array.isArray(result.results)) {
                result.results.forEach((res: any, idx: number) => {
                    const nodeId = workflow.nodes[idx]?.id;
                    if (nodeId) {
                        setExecutionStatus(prev => ({
                            ...prev!,
                            nodeStatuses: { ...prev!.nodeStatuses, [nodeId]: res.error ? 'failed' : 'completed' },
                            nodeProgress: { ...prev!.nodeProgress, [nodeId]: 100 },
                            nodeResults: { ...prev!.nodeResults, [nodeId]: res.result },
                            nodeErrors: res.error ? { ...prev!.nodeErrors, [nodeId]: res.error } : prev!.nodeErrors,
                            logs: [...(prev?.logs || []), {
                                timestamp: Date.now(),
                                nodeId: nodeId,
                                message: res.error ? `执行失败: ${res.error}` : `执行完成`,
                                level: res.error ? 'error' as const : 'info' as const
                            }]
                        }));
                    }
                });
            }

            // 添加完成日志
            setExecutionStatus(prev => ({
                ...prev!,
                logs: [...(prev?.logs || []), {
                    timestamp: Date.now(),
                    nodeId: 'system',
                    message: '工作流执行完成',
                    level: 'info' as const
                }]
            }));

            // 将结果作为消息添加到对话中
            onSend(
                `工作流执行完成。结果：\n${JSON.stringify(result, null, 2)}`,
                {
                    enableSearch: false,
                    enableThinking: false,
                    enableCodeExecution: false,
                    imageAspectRatio: '1:1',
                    imageResolution: '1024x1024'
                },
                [],
                'multi-agent'
            );
        } catch (error) {
            console.error('[MultiAgent] 工作流执行错误:', error);
            const errorMessage = error instanceof Error ? error.message : String(error);
            
            // 更新所有节点状态为失败
            setExecutionStatus(prev => {
                if (!prev) return prev;
                const newStatuses: Record<string, 'pending' | 'running' | 'completed' | 'failed'> = {};
                Object.keys(prev.nodeStatuses).forEach(nodeId => {
                    newStatuses[nodeId] = 'failed';
                });
                return {
                    ...prev,
                    nodeStatuses: newStatuses,
                    logs: [...prev.logs, {
                        timestamp: Date.now(),
                        nodeId: 'system',
                        message: `工作流执行失败: ${errorMessage}`,
                        level: 'error' as const
                    }]
                };
            });
            
            showError(`工作流执行失败: ${errorMessage}`);
        }
    }, [onSend, showError]);

    // ✅ 重置参数
    const resetParams = useCallback(() => {
        setPrompt('');
        setActiveAttachments([]);
    }, []);

    // ✅ 发送聊天消息
    const handleGenerate = useCallback(() => {
        if (!prompt.trim() || loadingState !== 'idle') return;
        
        const options: ChatOptions = {
            enableSearch: false,
            enableThinking: false,
            enableCodeExecution: false,
        };
        
        onSend(prompt, options, activeAttachments, appMode);
        setPrompt('');
        setActiveAttachments([]);
    }, [prompt, loadingState, activeAttachments, appMode, onSend]);

    // ✅ 键盘快捷键
    const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleGenerate();
        }
    }, [handleGenerate]);

    // ✅ 聊天模式的参数面板
    const chatParameterPanel = (
        <div className="w-72 flex-shrink-0 border-l border-slate-800 bg-slate-900/50 flex flex-col h-full overflow-hidden">
            {/* 头部 */}
            <div className="px-4 py-3 border-b border-slate-800/50 flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <SlidersHorizontal size={14} className="text-teal-400" />
                    <span className="text-xs font-bold text-white">对话参数</span>
                </div>
                <button
                    onClick={resetParams}
                    className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
                    title="重置"
                >
                    <RotateCcw size={12} />
                </button>
            </div>

            {/* 参数滚动区 */}
            <div className="flex-1 overflow-y-auto custom-scrollbar p-4 space-y-4">
                {/* 模型信息 */}
                {activeModelConfig && (
                    <div className="p-3 bg-slate-800/50 rounded-lg border border-slate-700/50">
                        <p className="text-xs text-slate-400">当前模型</p>
                        <p className="text-sm text-slate-200 font-medium mt-1">{activeModelConfig.name}</p>
                    </div>
                )}
            </div>

            {/* 底部固定区：附件预览 + 提示词 + 发送按钮 */}
            <div className="border-t border-slate-800 p-3 space-y-2 bg-slate-900/80">
                {/* 附件预览区 */}
                {activeAttachments.length > 0 && (
                    <div className="flex gap-2 flex-wrap">
                        {activeAttachments.map((att, idx) => (
                            <div key={idx} className="relative group flex items-center gap-2 bg-slate-800 rounded-lg px-2 py-1">
                                <FileText size={14} className="text-teal-400" />
                                <span className="text-xs text-slate-300 max-w-[100px] truncate">{att.name}</span>
                                <button
                                    onClick={() => {
                                        setActiveAttachments(activeAttachments.filter((_, i) => i !== idx));
                                    }}
                                    className="p-0.5 hover:bg-red-500/20 rounded text-slate-400 hover:text-red-400 transition-colors"
                                >
                                    <X size={12} />
                                </button>
                            </div>
                        ))}
                    </div>
                )}

                {/* 上传按钮 + 提示词输入 */}
                <div className="flex gap-2 items-end">
                    <label className="p-2.5 rounded-lg bg-slate-800 hover:bg-slate-700 cursor-pointer transition-colors border border-slate-700 flex-shrink-0">
                        <input
                            type="file"
                            accept="image/*,application/pdf,text/*"
                            multiple
                            className="hidden"
                            onChange={(e) => {
                                const files = Array.from(e.target.files || []);
                                const newAtts = files.map(file => ({
                                    id: `att-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
                                    name: file.name,
                                    mimeType: file.type,
                                    file: file,
                                }));
                                setActiveAttachments([...activeAttachments, ...newAtts]);
                                e.target.value = '';
                            }}
                        />
                        <Paperclip size={18} className="text-slate-400" />
                    </label>

                    <textarea
                        ref={textareaRef}
                        value={prompt}
                        onChange={(e) => {
                            setPrompt(e.target.value);
                            e.target.style.height = 'auto';
                            e.target.style.height = Math.min(e.target.scrollHeight, 150) + 'px';
                        }}
                        onKeyDown={handleKeyDown}
                        placeholder="输入消息..."
                        className="flex-1 min-h-[40px] max-h-[150px] bg-slate-800/80 border border-slate-700 rounded-lg p-2.5 text-sm text-slate-200 placeholder-slate-500 resize-none focus:outline-none focus:border-teal-500/50 focus:ring-1 focus:ring-teal-500/20 overflow-y-auto"
                    />
                </div>

                {/* 发送按钮 */}
                <button
                    onClick={handleGenerate}
                    disabled={!prompt.trim() || loadingState !== 'idle'}
                    className="w-full py-2.5 px-4 bg-gradient-to-r from-teal-600 to-cyan-600 hover:from-teal-500 hover:to-cyan-500 text-white rounded-xl font-medium text-sm flex items-center justify-center gap-2 shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    {loadingState !== 'idle' ? (
                        <>
                            <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                            处理中...
                        </>
                    ) : (
                        <>
                            <Send size={18} />
                            发送
                        </>
                    )}
                </button>
            </div>
        </div>
    );

    return (
        <GenViewLayout
            sidebarHeaderIcon={<Network size={16} className="text-teal-400" />}
            sidebarTitle="工作流历史"
            sidebar={
                <div className="p-4 space-y-4">
                    {/* 工作流历史 */}
                    <div>
                        <h3 className="text-xs font-semibold text-slate-300 mb-2 uppercase tracking-wider">工作流历史</h3>
                        <div className="space-y-2">
                            <div className="p-2 bg-slate-800/50 rounded border border-slate-700 cursor-pointer hover:bg-slate-800 transition-colors">
                                <div className="text-xs font-medium text-slate-200">示例工作流 1</div>
                                <div className="text-[10px] text-slate-500 mt-1">2 小时前</div>
                            </div>
                            <div className="p-2 bg-slate-800/50 rounded border border-slate-700 cursor-pointer hover:bg-slate-800 transition-colors">
                                <div className="text-xs font-medium text-slate-200">示例工作流 2</div>
                                <div className="text-[10px] text-slate-500 mt-1">昨天</div>
                            </div>
                        </div>
                    </div>
                    
                    {/* 模板库 */}
                    <div>
                        <h3 className="text-xs font-semibold text-slate-300 mb-2 uppercase tracking-wider">模板库</h3>
                        <div className="space-y-2">
                            <div className="p-2 bg-slate-800/50 rounded border border-slate-700 cursor-pointer hover:bg-slate-800 transition-colors">
                                <div className="text-xs font-medium text-slate-200">图像编辑工作流</div>
                                <div className="text-[10px] text-slate-500 mt-1">预定义模板</div>
                            </div>
                            <div className="p-2 bg-slate-800/50 rounded border border-slate-700 cursor-pointer hover:bg-slate-800 transition-colors">
                                <div className="text-xs font-medium text-slate-200">Excel 分析工作流</div>
                                <div className="text-[10px] text-slate-500 mt-1">预定义模板</div>
                            </div>
                        </div>
                    </div>
                </div>
            }
            sidebarExtraHeader={
                <div className="flex items-center gap-2">
                    <button
                        onClick={() => setViewMode(viewMode === 'editor' ? 'chat' : 'editor')}
                        className="p-1.5 hover:bg-slate-800 rounded-lg text-slate-400 hover:text-white transition-colors"
                        title={viewMode === 'editor' ? '切换到聊天视图' : '切换到编辑器视图'}
                    >
                        <MessageSquare size={16} />
                    </button>
                </div>
            }
            main={
                <div className="flex-1 flex flex-row h-full relative">
                    {/* ========== 左侧：主内容区 ========== */}
                    <div className="flex-1 flex flex-col h-full">
                        {/* 顶部工具栏 */}
                        <div className="shrink-0 border-b border-slate-700/50 bg-slate-900/50 backdrop-blur-sm">
                            <div className="flex items-center justify-between p-3">
                                <div className="flex items-center gap-3">
                                    <h2 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
                                        <Network size={18} className="text-teal-400" />
                                        多智能体工作流编排
                                    </h2>
                                    <div className="flex items-center gap-2 text-xs text-slate-400">
                                        <span className="px-2 py-1 bg-slate-800/50 rounded">
                                            {viewMode === 'editor' ? '编辑器视图' : '聊天视图'}
                                        </span>
                                    </div>
                                </div>
                                <button
                                    onClick={() => setAppMode('chat')}
                                    className="p-2 hover:bg-slate-800 rounded-lg text-slate-400 hover:text-white transition-colors"
                                    title="返回聊天模式"
                                >
                                    <X size={18} />
                                </button>
                            </div>
                        </div>

                        {/* 主内容区 */}
                        <div className="flex-1 overflow-hidden">
                            {viewMode === 'editor' ? (
                                <Suspense fallback={<LoadingSpinner />}>
                                    <MultiAgentWorkflowEditor
                                        onExecute={handleWorkflowExecute}
                                        onSave={async (workflow) => {
                                            // 工作流保存功能（可以保存为模板）
                                            console.log('[MultiAgentView] Saving workflow:', workflow);
                                        }}
                                        executionStatus={executionStatus}
                                    />
                                </Suspense>
                            ) : (
                                <div className="h-full overflow-y-auto custom-scrollbar">
                                    {messages.length === 0 ? (
                                        <div className="flex items-center justify-center h-full">
                                            <div className="text-center text-slate-500">
                                                <MessageSquare size={48} className="mx-auto mb-4 opacity-50" />
                                                <p className="text-sm">暂无聊天消息</p>
                                                <p className="text-xs mt-2 text-slate-600">切换到编辑器视图创建工作流</p>
                                            </div>
                                        </div>
                                    ) : (
                                        <div className="w-full max-w-[98%] 2xl:max-w-[1400px] mx-auto min-h-full flex flex-col p-4">
                                            <div className="flex-1 space-y-4 pb-4">
                                                {messages.map((msg, idx) => {
                                                    const isStreaming = loadingState === 'streaming' && idx === messages.length - 1 && msg.role === Role.MODEL;
                                                    return (
                                                        <MessageItem 
                                                            key={msg.id} 
                                                            message={msg} 
                                                            onImageClick={onImageClick}
                                                            onEditImage={onEditImage}
                                                            isStreaming={isStreaming}
                                                        />
                                                    );
                                                })}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            )}
                        </div>
                    </div>

                    {/* ========== 右侧：参数面板（仅聊天模式显示） ========== */}
                    {viewMode === 'chat' && chatParameterPanel}
                </div>
            }
            isMobileHistoryOpen={isMobileHistoryOpen}
            setIsMobileHistoryOpen={setIsMobileHistoryOpen}
        />
    );
});

MultiAgentView.displayName = 'MultiAgentView';
