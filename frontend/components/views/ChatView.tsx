
import React, { useRef, useEffect } from 'react';
import MessageItem from '../chat/MessageItem';
import InputArea from '../chat/InputArea';
import { WelcomeScreen } from '../layout/WelcomeScreen';
import { Message, ModelConfig, AppMode, ChatOptions, Attachment, Role } from '../../types/types';

interface ChatViewProps {
    messages: Message[];
    isLoadingModels: boolean;
    visibleModels: ModelConfig[];
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
    setAppMode: (mode: AppMode) => void;
    providerId?: string;
}

export const ChatView: React.FC<ChatViewProps> = ({
    messages,
    isLoadingModels,
    visibleModels,
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
    setAppMode,
    providerId
}) => {
    const messagesEndRef = useRef<HTMLDivElement>(null);

    // Auto-scroll logic
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
    }, [messages, loadingState]);

    return (
        <div className="flex-1 flex flex-col h-full relative">
            <main className="flex-1 overflow-y-auto p-0 scroll-smooth relative custom-scrollbar">
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
                    mode="chat"
                    setMode={setAppMode}
                    providerId={providerId}
                />
            </div>
        </div>
    );
};
