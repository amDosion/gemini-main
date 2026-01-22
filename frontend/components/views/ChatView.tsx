
import React, { useRef, useEffect, useCallback } from 'react';
import MessageItem from '../chat/MessageItem';
import InputArea from '../chat/InputArea';
import { WelcomeScreen } from '../layout/WelcomeScreen';
import { Message, ModelConfig, AppMode, ChatOptions, Attachment, Role } from '../../types/types';

interface ChatViewProps {
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
    onStop: () => void; // Updated prop definition
    activeModelConfig?: ModelConfig;
    appMode: AppMode; // ✅ 新增：接收当前应用模式
    setAppMode: (mode: AppMode) => void;
    providerId?: string;
}

export const ChatView: React.FC<ChatViewProps> = React.memo(({
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
    appMode, // ✅ 新增：接收当前应用模式
    setAppMode,
    providerId
}) => {
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const scrollContainerRef = useRef<HTMLDivElement>(null);
    const lastMessageCountRef = useRef(messages.length);
    const lastUserMessageIdRef = useRef<string | null>(null);
    const shouldAutoScrollRef = useRef(true);
    const scrollRafRef = useRef<number | null>(null);
    // 新增：用于检测用户主动滚动
    const userScrolledUpRef = useRef(false);
    const lastScrollTopRef = useRef(0);

    const updateAutoScroll = useCallback(() => {
        const container = scrollContainerRef.current;
        if (!container) return;

        const { scrollTop, scrollHeight, clientHeight } = container;
        const distanceFromBottom = scrollHeight - scrollTop - clientHeight;
        
        // 检测用户主动向上滚动（scrollTop 减少超过 10px）
        const scrollDelta = scrollTop - lastScrollTopRef.current;
        
        if (scrollDelta < -10) {
            // 用户主动向上滚动，停止自动滚动
            userScrolledUpRef.current = true;
            shouldAutoScrollRef.current = false;
        } else if (distanceFromBottom < 50) {
            // 用户滚动到底部附近，重新启用自动滚动
            userScrolledUpRef.current = false;
            shouldAutoScrollRef.current = true;
        } else if (!userScrolledUpRef.current) {
            // 非用户主动滚动，使用宽松阈值（流式传输期间 300px，否则 120px）
            const threshold = loadingState === 'streaming' ? 300 : 120;
            shouldAutoScrollRef.current = distanceFromBottom < threshold;
        }
        
        lastScrollTopRef.current = scrollTop;
    }, [loadingState]);

    // Initialize auto-scroll state (in case user starts mid-history)
    useEffect(() => {
        updateAutoScroll();
    }, [updateAutoScroll]);

    // Auto-scroll behavior:
    // - Always scroll when the user sends a message
    // - During streaming, keep "pinned to bottom" unless the user scrolls up
    useEffect(() => {
        if (scrollRafRef.current !== null) {
            cancelAnimationFrame(scrollRafRef.current);
            scrollRafRef.current = null;
        }

        const container = scrollContainerRef.current;
        if (!container) return;

        // Detect if a new user message was added (user just sent a message)
        const lastMessage = messages[messages.length - 1];
        const isNewUserMessage =
            !!lastMessage &&
            lastMessage.role === Role.USER &&
            lastMessage.id !== lastUserMessageIdRef.current &&
            messages.length > lastMessageCountRef.current;

        // Update refs
        lastMessageCountRef.current = messages.length;
        if (isNewUserMessage) {
            lastUserMessageIdRef.current = lastMessage.id;
            shouldAutoScrollRef.current = true; // force pin to bottom after sending
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

    return (
        <div className="flex-1 flex flex-col h-full relative">
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
                                // Determine if this message is currently streaming
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
                            
                            {/* Only show separate loader for 'loading' state (e.g. image gen, or initial connection before stream) */}
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

            {/* Input Area Overlay */}
            <div className="relative z-20 shrink-0">
                <div className="absolute bottom-full w-full h-12 bg-gradient-to-t from-slate-950 to-transparent pointer-events-none" />
                <InputArea
                    onSend={onSend}
                    isLoading={loadingState !== 'idle'}
                    onStop={onStop} // Pass the real stop handler
                    currentModel={activeModelConfig}
                    visibleModels={visibleModels}
                    allVisibleModels={allVisibleModels}  // ✅ 传递完整模型列表
                    mode={appMode} // ✅ 修复：使用传入的 appMode 而不是硬编码 "chat"
                    setMode={setAppMode}
                    providerId={providerId}
                />
            </div>
        </div>
    );
});
