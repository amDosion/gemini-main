
import React, { useRef, useEffect, useCallback, useState } from 'react';
import MessageItem from '../chat/MessageItem';
import ChatInputArea from '../chat/ChatInputArea';
import { WelcomeScreen } from '../layout/WelcomeScreen';
import { Message, ModelConfig, AppMode, ChatOptions, Attachment, Role } from '../../types/types';
import { Thermometer, Hash, Percent, Layers, RotateCcw, SlidersHorizontal } from 'lucide-react';

interface ChatViewProps {
    messages: Message[];
    isLoadingModels: boolean;
    visibleModels: ModelConfig[];
    allVisibleModels?: ModelConfig[];
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
    providerId?: string;
}

export const ChatView: React.FC<ChatViewProps> = React.memo(({
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

    // ✅ Chat 模式生成参数状态
    const [temperature, setTemperature] = useState<number>(0.7);
    const [maxTokens, setMaxTokens] = useState<number>(8192);
    const [topP, setTopP] = useState<number>(0.95);
    const [topK, setTopK] = useState<number>(40);

    // 重置参数到默认值
    const resetParams = useCallback(() => {
        setTemperature(0.7);
        setMaxTokens(8192);
        setTopP(0.95);
        setTopK(40);
    }, []);

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
        <div className="flex-1 flex h-full relative">
            {/* ========== 左侧：消息区域 + 输入框 ========== */}
            <div className="flex-1 flex flex-col min-w-0">
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

                {/* Input Area - 使用 Chat 专用版本（无模式切换） */}
                <ChatInputArea
                    onSend={onSend}
                    isLoading={loadingState !== 'idle'}
                    onStop={onStop}
                    currentModel={activeModelConfig}
                    visibleModels={visibleModels}
                    allVisibleModels={allVisibleModels}
                    mode={appMode}
                    providerId={providerId}
                    // ✅ 传递生成参数
                    temperature={temperature}
                    maxTokens={maxTokens}
                    topP={topP}
                    topK={topK}
                />
            </div>

            {/* ========== 右侧：控制面板 ========== */}
            <div className="w-72 flex-shrink-0 border-l border-slate-800 bg-slate-900/30 flex flex-col h-full overflow-hidden">
                {/* 头部 */}
                <div className="px-4 py-3 border-b border-slate-800/50 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <SlidersHorizontal size={14} className="text-indigo-400" />
                        <span className="text-xs font-bold text-white">生成参数</span>
                    </div>
                    <button
                        onClick={resetParams}
                        className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
                        title="重置为默认值"
                    >
                        <RotateCcw size={12} />
                    </button>
                </div>
                
                {/* 参数区域 */}
                <div className="flex-1 overflow-y-auto p-4 space-y-5 custom-scrollbar">
                    {/* Temperature */}
                    <div className="space-y-2">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <Thermometer size={12} className="text-orange-400" />
                                <span className="text-xs text-slate-300">Temperature</span>
                            </div>
                            <span className="text-xs text-indigo-400 font-mono">{temperature.toFixed(2)}</span>
                        </div>
                        <input
                            type="range"
                            min="0"
                            max="2"
                            step="0.05"
                            value={temperature}
                            onChange={(e) => setTemperature(parseFloat(e.target.value))}
                            className="w-full h-1.5 bg-slate-700 rounded-full appearance-none cursor-pointer accent-indigo-500"
                        />
                        <div className="flex justify-between text-[10px] text-slate-500">
                            <span>精确</span>
                            <span>平衡</span>
                            <span>创意</span>
                        </div>
                    </div>

                    {/* Max Tokens */}
                    <div className="space-y-2">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <Hash size={12} className="text-emerald-400" />
                                <span className="text-xs text-slate-300">Max Tokens</span>
                            </div>
                            <span className="text-xs text-indigo-400 font-mono">{maxTokens.toLocaleString()}</span>
                        </div>
                        <input
                            type="range"
                            min="256"
                            max="32768"
                            step="256"
                            value={maxTokens}
                            onChange={(e) => setMaxTokens(parseInt(e.target.value))}
                            className="w-full h-1.5 bg-slate-700 rounded-full appearance-none cursor-pointer accent-indigo-500"
                        />
                        <div className="flex justify-between text-[10px] text-slate-500">
                            <span>256</span>
                            <span>8K</span>
                            <span>32K</span>
                        </div>
                    </div>

                    {/* Top P */}
                    <div className="space-y-2">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <Percent size={12} className="text-blue-400" />
                                <span className="text-xs text-slate-300">Top P</span>
                            </div>
                            <span className="text-xs text-indigo-400 font-mono">{topP.toFixed(2)}</span>
                        </div>
                        <input
                            type="range"
                            min="0"
                            max="1"
                            step="0.05"
                            value={topP}
                            onChange={(e) => setTopP(parseFloat(e.target.value))}
                            className="w-full h-1.5 bg-slate-700 rounded-full appearance-none cursor-pointer accent-indigo-500"
                        />
                        <div className="flex justify-between text-[10px] text-slate-500">
                            <span>0.0</span>
                            <span>0.5</span>
                            <span>1.0</span>
                        </div>
                    </div>

                    {/* Top K */}
                    <div className="space-y-2">
                        <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                                <Layers size={12} className="text-purple-400" />
                                <span className="text-xs text-slate-300">Top K</span>
                            </div>
                            <span className="text-xs text-indigo-400 font-mono">{topK}</span>
                        </div>
                        <input
                            type="range"
                            min="1"
                            max="100"
                            step="1"
                            value={topK}
                            onChange={(e) => setTopK(parseInt(e.target.value))}
                            className="w-full h-1.5 bg-slate-700 rounded-full appearance-none cursor-pointer accent-indigo-500"
                        />
                        <div className="flex justify-between text-[10px] text-slate-500">
                            <span>1</span>
                            <span>50</span>
                            <span>100</span>
                        </div>
                    </div>

                    {/* 参数说明 */}
                    <div className="pt-2 border-t border-slate-800/50">
                        <p className="text-[10px] text-slate-500 leading-relaxed">
                            <strong className="text-slate-400">Temperature</strong>: 控制回复的随机性，值越高越有创意。<br/>
                            <strong className="text-slate-400">Max Tokens</strong>: 最大输出长度。<br/>
                            <strong className="text-slate-400">Top P/K</strong>: 采样参数，影响词汇选择的多样性。
                        </p>
                    </div>
                </div>
            </div>
        </div>
    );
});
