import React, { useRef, useEffect, useCallback, useState, useMemo } from 'react';
import MessageItem from '../chat/MessageItem';
import { WelcomeScreen } from '../layout/WelcomeScreen';
import { Message, ModelConfig, AppMode, ChatOptions, Attachment, Role } from '../../types/types';
import ResearchProgressIndicator from '../research/ResearchProgressIndicator';
import { useMessageProcessor } from '../../hooks/useMessageProcessor';
import { SlidersHorizontal, RotateCcw, Send, Paperclip, X, FileText } from 'lucide-react';
// Multi-Agent 相关导入已移除，multi-agent 模式现在使用独立的 MultiAgentView 组件

interface AgentViewProps {
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

export const AgentView: React.FC<AgentViewProps> = React.memo(({
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
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const scrollContainerRef = useRef<HTMLDivElement>(null);
    const textareaRef = useRef<HTMLTextAreaElement>(null);
    const lastMessageCountRef = useRef(messages.length);
    const lastUserMessageIdRef = useRef<string | null>(null);
    const shouldAutoScrollRef = useRef(true);
    const scrollRafRef = useRef<number | null>(null);
    const userScrolledUpRef = useRef(false);
    const lastScrollTopRef = useRef(0);
    const [researchStartTime, setResearchStartTime] = useState<number | null>(null);
    const [elapsedTime, setElapsedTime] = useState(0);
    
    // ✅ 参数面板状态
    const [prompt, setPrompt] = useState('');
    const [activeAttachments, setActiveAttachments] = useState<Attachment[]>([]);
    const [enableSearch, setEnableSearch] = useState(true);
    const [enableThinking, setEnableThinking] = useState(true);

    // 获取最后一个模型消息用于显示研究状态
    const lastModelMessage = useMemo(() => {
        return messages.filter(msg => msg.role === Role.MODEL).pop();
    }, [messages]);

    // 处理最后一个模型消息的思考内容
    // ✅ 修复：Hooks 必须在每次渲染时以相同顺序调用，不能条件调用
    // 创建一个空消息作为 fallback，确保 useMessageProcessor 总是被调用
    const fallbackMessage: Message = {
        id: '',
        role: Role.MODEL,
        content: '',
        timestamp: Date.now(),
        mode: 'deep-research'
    };
    const messageToProcess = lastModelMessage || fallbackMessage;
    const lastModelMessageProcessor = useMessageProcessor(messageToProcess);

    // 从消息中提取研究状态信息
    const researchStatus = useMemo(() => {
        // ✅ 修复：检查是否有有效的消息（不是 fallback）
        if (!lastModelMessage) {
            return null;
        }

        const { thinkingContent } = lastModelMessageProcessor;
        const isStreaming = loadingState === 'streaming';
        const hasContent = lastModelMessage.content && lastModelMessage.content.trim().length > 0;
        const hasThinking = thinkingContent && thinkingContent.trim().length > 0;

        if (isStreaming) {
            if (hasThinking && !hasContent) {
                return {
                    status: 'in_progress' as const,
                    progress: '正在思考和分析...'
                };
            } else if (hasContent) {
                return {
                    status: 'in_progress' as const,
                    progress: '正在生成研究结果...'
                };
            } else {
                return {
                    status: 'starting' as const,
                    progress: '正在启动研究...'
                };
            }
        } else if (hasContent && !isStreaming) {
            return {
                status: 'completed' as const,
                progress: '研究已完成'
            };
        }

        return null;
    }, [lastModelMessage, lastModelMessageProcessor, loadingState]);

    // 跟踪研究开始时间
    useEffect(() => {
        if (loadingState === 'streaming' && researchStartTime === null) {
            setResearchStartTime(Date.now());
        } else if (loadingState === 'idle' && researchStartTime !== null) {
            setResearchStartTime(null);
            setElapsedTime(0);
        }
    }, [loadingState, researchStartTime]);

    // 更新已用时间
    useEffect(() => {
        if (researchStartTime === null) return;

        const interval = setInterval(() => {
            const elapsed = Math.floor((Date.now() - researchStartTime) / 1000);
            setElapsedTime(elapsed);
        }, 1000);

        return () => clearInterval(interval);
    }, [researchStartTime]);

    const updateAutoScroll = useCallback(() => {
        const container = scrollContainerRef.current;
        if (!container) return;

        const { scrollTop, scrollHeight, clientHeight } = container;
        const distanceFromBottom = scrollHeight - scrollTop - clientHeight;
        
        const scrollDelta = scrollTop - lastScrollTopRef.current;
        
        if (scrollDelta < -10) {
            userScrolledUpRef.current = true;
            shouldAutoScrollRef.current = false;
        } else if (distanceFromBottom < 50) {
            userScrolledUpRef.current = false;
            shouldAutoScrollRef.current = true;
        } else if (!userScrolledUpRef.current) {
            const threshold = loadingState === 'streaming' ? 300 : 120;
            shouldAutoScrollRef.current = distanceFromBottom < threshold;
        }
        
        lastScrollTopRef.current = scrollTop;
    }, [loadingState]);

    useEffect(() => {
        updateAutoScroll();
    }, [updateAutoScroll]);

    useEffect(() => {
        if (scrollRafRef.current !== null) {
            cancelAnimationFrame(scrollRafRef.current);
            scrollRafRef.current = null;
        }

        const container = scrollContainerRef.current;
        if (!container) return;

        const lastMessage = messages[messages.length - 1];
        const isNewUserMessage =
            !!lastMessage &&
            lastMessage.role === Role.USER &&
            lastMessage.id !== lastUserMessageIdRef.current &&
            messages.length > lastMessageCountRef.current;

        lastMessageCountRef.current = messages.length;
        if (isNewUserMessage) {
            lastUserMessageIdRef.current = lastMessage.id;
            shouldAutoScrollRef.current = true;
        }

        const shouldScroll = isNewUserMessage || shouldAutoScrollRef.current;
        if (!shouldScroll) return;

        const behavior: ScrollBehavior = loadingState === 'streaming' ? 'auto' : 'smooth';

        scrollRafRef.current = requestAnimationFrame(() => {
            messagesEndRef.current?.scrollIntoView({
                behavior,
                block: 'end',
            });
            scrollRafRef.current = null;
        });

        return () => {
            if (scrollRafRef.current !== null) {
                cancelAnimationFrame(scrollRafRef.current);
                scrollRafRef.current = null;
            }
        };
    }, [messages, loadingState]);

    // ✅ AgentView 现在只用于 deep-research 模式
    // multi-agent 模式使用独立的 MultiAgentView 组件

    // ✅ 重置参数
    const resetParams = useCallback(() => {
        setEnableSearch(true);
        setEnableThinking(true);
        setPrompt('');
        setActiveAttachments([]);
    }, []);

    // ✅ 发送研究请求
    const handleGenerate = useCallback(() => {
        if (!prompt.trim() || loadingState !== 'idle') return;
        
        const options: ChatOptions = {
            enableSearch,
            enableThinking,
            enableCodeExecution: false,
            imageAspectRatio: '1:1',
            imageResolution: '1024x1024',
        };
        
        onSend(prompt, options, activeAttachments, appMode);
        setPrompt('');
        setActiveAttachments([]);
    }, [prompt, loadingState, enableSearch, enableThinking, activeAttachments, appMode, onSend]);

    // ✅ 键盘快捷键
    const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleGenerate();
        }
    }, [handleGenerate]);

    return (
        <div className="flex-1 flex flex-row h-full relative">
            {/* ========== 左侧：消息区域 ========== */}
            <div className="flex-1 flex flex-col h-full">
                {/* 研究进度指示器区域（顶部固定） */}
                {researchStatus && loadingState !== 'idle' && (
                    <div className="shrink-0 border-b border-slate-700/50 bg-slate-900/50 backdrop-blur-sm">
                        <div className="w-full max-w-[98%] 2xl:max-w-[1400px] mx-auto p-4">
                            <ResearchProgressIndicator
                                status={researchStatus.status}
                                elapsedTime={elapsedTime}
                                progress={researchStatus.progress}
                            />
                        </div>
                    </div>
                )}

                {/* 消息列表区域（中间可滚动） */}
                <main 
                    ref={scrollContainerRef}
                    onScroll={updateAutoScroll}
                    className={`flex-1 overflow-y-auto p-0 relative custom-scrollbar ${loadingState === 'streaming' ? '' : 'scroll-smooth'}`}
                >
                    {messages.length === 0 ? (
                        <WelcomeScreen 
                            apiKey={apiKey}
                            isLoadingModels={isLoadingModels}
                            visibleModels={visibleModels}
                            onPromptSelect={onPromptSelect}
                            onOpenSettings={onOpenSettings}
                            protocol={protocol}
                        />
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
                                
                                {loadingState === 'loading' && (
                                    <div className="flex justify-start mb-6">
                                        <div className="flex items-center gap-2 bg-slate-800/50 px-4 py-3 rounded-2xl rounded-tl-none border border-slate-700/50">
                                            <div className="w-2 h-2 bg-indigo-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
                                            <div className="w-2 h-2 bg-indigo-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
                                            <div className="w-2 h-2 bg-indigo-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
                                        </div>
                                    </div>
                                )}
                                <div ref={messagesEndRef} className="h-4" />
                            </div>
                        </div>
                    )}
                </main>
            </div>

            {/* ========== 右侧：参数面板 ========== */}
            <div className="w-72 flex-shrink-0 border-l border-slate-800 bg-slate-900/50 flex flex-col h-full overflow-hidden">
                {/* 头部 */}
                <div className="px-4 py-3 border-b border-slate-800/50 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <SlidersHorizontal size={14} className="text-indigo-400" />
                        <span className="text-xs font-bold text-white">研究参数</span>
                    </div>
                    <button
                        onClick={resetParams}
                        className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
                        title="重置为默认值"
                    >
                        <RotateCcw size={12} />
                    </button>
                </div>

                {/* 参数滚动区 */}
                <div className="flex-1 overflow-y-auto custom-scrollbar p-4 space-y-4">
                    {/* 搜索开关 */}
                    <div className="flex items-center justify-between py-1">
                        <span className="text-xs text-slate-300">启用搜索</span>
                        <div
                            onClick={() => setEnableSearch(!enableSearch)}
                            className={`w-10 h-6 flex items-center rounded-full p-1 cursor-pointer transition-colors duration-200 ${
                                enableSearch ? 'bg-indigo-600' : 'bg-slate-600'
                            }`}
                        >
                            <div className={`w-4 h-4 bg-white rounded-full shadow-md transform transition-transform duration-200 ${
                                enableSearch ? 'translate-x-4' : 'translate-x-0'
                            }`} />
                        </div>
                    </div>

                    {/* 思考开关 */}
                    <div className="flex items-center justify-between py-1">
                        <span className="text-xs text-slate-300">启用思考</span>
                        <div
                            onClick={() => setEnableThinking(!enableThinking)}
                            className={`w-10 h-6 flex items-center rounded-full p-1 cursor-pointer transition-colors duration-200 ${
                                enableThinking ? 'bg-indigo-600' : 'bg-slate-600'
                            }`}
                        >
                            <div className={`w-4 h-4 bg-white rounded-full shadow-md transform transition-transform duration-200 ${
                                enableThinking ? 'translate-x-4' : 'translate-x-0'
                            }`} />
                        </div>
                    </div>

                    {/* 模型信息 */}
                    {activeModelConfig && (
                        <div className="p-3 bg-slate-800/50 rounded-lg border border-slate-700/50">
                            <p className="text-xs text-slate-400">当前模型</p>
                            <p className="text-sm text-slate-200 font-medium mt-1">{activeModelConfig.name}</p>
                        </div>
                    )}
                </div>

                {/* 底部固定区：附件预览 + 提示词 + 研究按钮 */}
                <div className="border-t border-slate-800 p-3 space-y-2 bg-slate-900/80">
                    {/* 附件预览区 */}
                    {activeAttachments.length > 0 && (
                        <div className="flex gap-2 flex-wrap">
                            {activeAttachments.map((att, idx) => (
                                <div key={idx} className="relative group flex items-center gap-2 bg-slate-800 rounded-lg px-2 py-1">
                                    <FileText size={14} className="text-indigo-400" />
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

                    {/* 提示词输入 */}
                    <textarea
                        ref={textareaRef}
                        value={prompt}
                        onChange={(e) => {
                            setPrompt(e.target.value);
                            e.target.style.height = 'auto';
                            e.target.style.height = Math.min(e.target.scrollHeight, 150) + 'px';
                        }}
                        onKeyDown={handleKeyDown}
                        placeholder="输入研究问题..."
                        className="w-full min-h-[40px] max-h-[150px] bg-slate-800/80 border border-slate-700 rounded-lg p-2.5 text-sm text-slate-200 placeholder-slate-500 resize-none focus:outline-none focus:border-indigo-500/50 focus:ring-1 focus:ring-indigo-500/20 overflow-y-auto"
                    />

                    {/* 上传按钮 + 研究按钮 */}
                    <div className="flex gap-2 items-center">
                        {/* 上传按钮 */}
                        <label className="p-2.5 rounded-lg bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 cursor-pointer transition-colors border border-indigo-500/50 flex-shrink-0 shadow-lg">
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
                            <Paperclip size={18} className="text-white" />
                        </label>

                        {/* 研究按钮 */}
                        <button
                            onClick={handleGenerate}
                            disabled={!prompt.trim() || loadingState !== 'idle'}
                            className="flex-1 py-2.5 px-4 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white rounded-xl font-medium text-sm flex items-center justify-center gap-2 shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {loadingState !== 'idle' ? (
                                <>
                                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                                    研究中...
                                </>
                            ) : (
                                <>
                                    <Send size={18} />
                                    开始研究
                                </>
                            )}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
});

AgentView.displayName = 'AgentView';
