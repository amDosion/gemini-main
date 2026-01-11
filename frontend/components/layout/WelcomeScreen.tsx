
import React from 'react';
import { Sparkles, Globe, Brain, Image as ImageIcon, PlaySquare, Settings, Loader2 } from 'lucide-react';
import { ModelConfig, AppMode } from '../../types/types';

interface WelcomeScreenProps {
    apiKey: string;
    isLoadingModels: boolean;
    visibleModels: ModelConfig[];
    onPromptSelect: (text: string, mode: AppMode, modelId: string, requiredCap: string) => void;
    onOpenSettings: () => void;
    protocol: string;
}

export const WelcomeScreen: React.FC<WelcomeScreenProps> = ({
    apiKey,
    isLoadingModels,
    visibleModels,
    onPromptSelect,
    onOpenSettings,
    protocol
}) => {
    return (
        <div className="flex-1 flex flex-col items-center justify-center text-center p-4 opacity-0 animate-[fadeIn_0.5s_ease-out_forwards]">
            <div className="w-16 h-16 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-2xl flex items-center justify-center mb-6 shadow-2xl shadow-indigo-500/20">
                <Sparkles size={32} className="text-white" />
            </div>
            <h2 className="text-2xl font-bold text-slate-100 mb-2">
                {apiKey ? 'How can I help you today?' : 'Welcome to Gemini Flux'}
            </h2>
            <p className="text-slate-400 mb-8 max-w-md">
                {apiKey 
                    ? 'Select a model or choose a mode below to get started.'
                    : 'Please click the Settings button in the sidebar to configure your Gemini API Key.'
                }
            </p>
            {apiKey ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3 w-full max-w-4xl">
                    {[
                        { text: "Find AI news", icon: Globe, requiredCap: 'search', mode: 'chat' },
                        { text: "Solve logic puzzle", icon: Brain, requiredCap: 'reasoning', mode: 'chat' },
                        { text: "Generate city image", icon: ImageIcon, requiredCap: 'vision', mode: 'image-gen' },
                        { text: "Generate cool video", icon: PlaySquare, requiredCap: 'vision', mode: 'video-gen' }
                    ].map((item) => {
                        const modelForTask = visibleModels.find(m => m.capabilities[item.requiredCap as keyof typeof m.capabilities]);
                        if (!modelForTask) return null;

                        return (
                        <button 
                            key={item.text}
                            onClick={() => onPromptSelect(item.text, item.mode as AppMode, modelForTask.id, item.requiredCap)}
                            className="p-4 bg-slate-800/40 hover:bg-slate-800 border border-slate-700/50 hover:border-indigo-500/50 rounded-xl text-sm text-slate-300 transition-all text-left flex items-center gap-3 group"
                        >
                            <div className="p-2 rounded-lg bg-slate-700 group-hover:bg-slate-600 text-slate-400 group-hover:text-white transition-colors shrink-0">
                                <item.icon size={16} />
                            </div>
                            <span className="truncate">{item.text}</span>
                        </button>
                        );
                    })}
                </div>
            ) : (
                <button 
                    onClick={onOpenSettings}
                    className="px-6 py-3 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl font-medium transition-all shadow-lg shadow-indigo-500/30 flex items-center gap-2"
                >
                    <Settings size={18} />
                    Configure API Key
                </button>
            )}

            {isLoadingModels && (
                <div className="mt-8 flex flex-col items-center justify-center text-slate-500 gap-3">
                    <Loader2 size={32} className="animate-spin text-indigo-500" />
                    <span>Connecting to {protocol === 'google' ? 'Gemini' : 'OpenAI Compatible Endpoint'}...</span>
                </div>
            )}
        </div>
    );
};
