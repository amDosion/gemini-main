import React, { useRef, useEffect, useCallback, useState, useMemo } from 'react';
import MessageItem from '../chat/MessageItem';
import InputArea from '../chat/InputArea';
import { WelcomeScreen } from '../layout/WelcomeScreen';
import { Message, ModelConfig, AppMode, ChatOptions, Attachment, Role } from '../../types/types';
import ResearchProgressIndicator, { ResearchProgressIndicatorProps } from '../research/ResearchProgressIndicator';
import { useMessageProcessor } from '../../hooks/useMessageProcessor';
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
    allVisibleModels = [],  // ✅ 新增
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
    const lastMessageCountRef = useRef(messages.length);
    const lastUserMessageIdRef = useRef<string | null>(null);
    const shouldAutoScrollRef = useRef(true);
    const scrollRafRef = useRef<number | null>(null);
    const userScrolledUpRef = useRef(false);
    const lastScrollTopRef = useRef(0);
    const [researchStartTime, setResearchStartTime] = useState<number | null>(null);
    const [elapsedTime, setElapsedTime] = useState(0);

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

    return (
        <div className="flex-1 flex flex-col h-full relative">
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

            {/* 输入区域（底部固定） */}
            <div className="relative z-20 shrink-0">
                <div className="absolute bottom-full w-full h-12 bg-gradient-to-t from-slate-950 to-transparent pointer-events-none" />
                <InputArea
                    onSend={onSend}
                    isLoading={loadingState !== 'idle'}
                    onStop={onStop}
                    currentModel={activeModelConfig}
                    visibleModels={visibleModels}
                    allVisibleModels={allVisibleModels}  // ✅ 传递完整模型列表
                    mode={appMode}
                    setMode={setAppMode}
                    providerId={providerId}
                />
            </div>
        </div>
    );
});

AgentView.displayName = 'AgentView';
