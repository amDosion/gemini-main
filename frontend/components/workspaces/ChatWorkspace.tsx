
import React, { useEffect, useRef } from 'react';
import MessageItem from '../chat/MessageItem';
import { WelcomeScreen } from '../layout/WelcomeScreen';
import { Message, ModelConfig, AppMode } from '../../types/types';

interface ChatWorkspaceProps {
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
}

export const ChatWorkspace: React.FC<ChatWorkspaceProps> = ({
  messages,
  isLoadingModels,
  visibleModels,
  apiKey,
  protocol,
  onPromptSelect,
  onOpenSettings,
  onImageClick,
  onEditImage,
  loadingState
}) => {
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loadingState]);

  if (messages.length === 0) {
    return (
      <WelcomeScreen 
        apiKey={apiKey}
        isLoadingModels={isLoadingModels}
        visibleModels={visibleModels}
        onPromptSelect={onPromptSelect}
        onOpenSettings={onOpenSettings}
        protocol={protocol}
      />
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 scroll-smooth">
      <div className="w-full max-w-[98%] 2xl:max-w-[1400px] mx-auto min-h-full flex flex-col">
        <div className="flex-1 space-y-2 pb-2">
          {messages.map((msg) => (
            <MessageItem 
              key={msg.id} 
              message={msg} 
              onImageClick={onImageClick}
              onEditImage={onEditImage}
            />
          ))}
          {loadingState !== 'idle' && loadingState !== 'uploading' && (
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
    </div>
  );
};
