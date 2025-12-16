
import React, { useState } from 'react';
import { PlusCircle, Database, Trash2, Edit3, Check, Layers, List, Copy, Zap, Cpu, Globe, Sparkles, Server, AlertTriangle, ChevronLeft, Loader2, Eye, Box } from 'lucide-react';
import { ConfigProfile } from '../../../services/db';
import { ModelConfig, ApiProtocol } from '../../../../types';
import { LLMFactory } from '../../../services/LLMFactory';
import { v4 as uuidv4 } from 'uuid';

interface ProfilesTabProps {
  profiles: ConfigProfile[];
  activeProfileId: string | null;
  onActivateProfile: (id: string) => Promise<void>;
  onDeleteProfile: (id: string) => Promise<void>;
  onSaveProfile: (profile: ConfigProfile) => Promise<void>; // Needed for duplicate/update
  onEditProfile: (profile: ConfigProfile) => void;
  onCreateNew: () => void;
}

export const ProfilesTab: React.FC<ProfilesTabProps> = ({
  profiles,
  activeProfileId,
  onActivateProfile,
  onDeleteProfile,
  onSaveProfile,
  onEditProfile,
  onCreateNew
}) => {
  // --- Local State for Inspection ---
  const [previewProfile, setPreviewProfile] = useState<ConfigProfile | null>(null);
  const [previewModels, setPreviewModels] = useState<ModelConfig[]>([]);
  const [isPreviewLoading, setIsPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  
  // --- Local State for Deletion ---
  const [deleteConfirmationId, setDeleteConfirmationId] = useState<string | null>(null);

  const getProviderIcon = (pid: string) => {
      if (pid.includes('google')) return <Zap size={20} />;
      if (pid.includes('deepseek')) return <Cpu size={20} />;
      if (pid.includes('tongyi')) return <Globe size={20} />;
      if (pid.includes('openai')) return <Sparkles size={20} />;
      return <Server size={20} />;
  };

  const handleDuplicate = (profile: ConfigProfile) => {
      const copy: ConfigProfile = {
          ...profile,
          id: uuidv4(),
          name: `${profile.name} (Copy)`,
          createdAt: Date.now(),
          updatedAt: Date.now()
      };
      onSaveProfile(copy);
  };

  const handleInspectProfile = async (profile: ConfigProfile) => {
      setPreviewProfile(profile);
      setPreviewError(null);
      setPreviewModels([]);

      // First check if we have saved models
      if (profile.savedModels && profile.savedModels.length > 0) {
          setPreviewModels(profile.savedModels);
          return;
      }

      // Otherwise fetch live
      setIsPreviewLoading(true);
      try {
          const providerInstance = LLMFactory.getProvider(profile.protocol as ApiProtocol, profile.providerId);
          const models = await providerInstance.getAvailableModels(profile.apiKey, profile.baseUrl);
          
          if (models.length > 0) {
              setPreviewModels(models);
              // Update cache count in background if it changed
              if (profile.cachedModelCount !== models.length) {
                  onSaveProfile({ ...profile, cachedModelCount: models.length, savedModels: models });
              }
          } else {
              setPreviewError("No models found. Check API Key or connectivity.");
          }
      } catch (e: any) {
          setPreviewError(e.message || "Failed to fetch models.");
      } finally {
          setIsPreviewLoading(false);
      }
  };

  // If inspecting, show the overlay
  if (previewProfile) {
      return (
        <div className="absolute inset-0 bg-slate-950 z-10 flex flex-col animate-[fadeIn_0.2s_ease-out]">
            <div className="flex items-center gap-3 p-4 border-b border-slate-800 bg-slate-900/50">
                <button 
                    onClick={() => setPreviewProfile(null)}
                    className="p-2 hover:bg-slate-800 rounded-full text-slate-400 hover:text-white"
                >
                    <ChevronLeft size={20} />
                </button>
                <div>
                    <h3 className="font-bold text-slate-200">Models for: {previewProfile.name}</h3>
                    <p className="text-xs text-slate-500">Live fetch using stored credentials</p>
                </div>
            </div>
            
            <div className="flex-1 overflow-y-auto p-4 custom-scrollbar">
                {isPreviewLoading ? (
                    <div className="flex flex-col items-center justify-center h-48 text-slate-500 gap-3">
                        <Loader2 size={24} className="animate-spin text-indigo-500" />
                        <span>Fetching models...</span>
                    </div>
                ) : previewError ? (
                    <div className="p-4 bg-red-900/20 border border-red-900/50 rounded-xl text-red-300 flex items-start gap-3">
                        <AlertTriangle size={18} className="mt-0.5" />
                        <div>
                            <div className="font-bold mb-1">Fetch Failed</div>
                            <div className="text-sm opacity-90">{previewError}</div>
                        </div>
                    </div>
                ) : (
                    <div className="space-y-2">
                        {previewModels.map(m => {
                            const isHidden = previewProfile.hiddenModels.includes(m.id);
                            return (
                                <div key={m.id} className={`p-3 rounded-xl border flex justify-between items-center ${
                                    isHidden 
                                    ? 'bg-slate-900/30 border-slate-800 opacity-60' 
                                    : 'bg-slate-900 border-slate-700'
                                }`}>
                                    <div className="flex items-center gap-3">
                                        <div className={`p-2 rounded-lg ${isHidden ? 'bg-slate-800 text-slate-600' : 'bg-indigo-500/10 text-indigo-400'}`}>
                                            {m.capabilities.vision ? <Eye size={16} /> : <Box size={16} />}
                                        </div>
                                        <div>
                                            <div className="text-sm font-medium text-slate-200">{m.name}</div>
                                            <div className="text-xs text-slate-500 font-mono">{m.id}</div>
                                        </div>
                                    </div>
                                    {isHidden && (
                                        <span className="text-[10px] bg-slate-800 px-2 py-1 rounded text-slate-500 font-medium">Hidden</span>
                                    )}
                                </div>
                            );
                        })}
                        {previewModels.length === 0 && !isPreviewLoading && (
                            <div className="text-center py-8 text-slate-500">No models returned by the API.</div>
                        )}
                    </div>
                )}
            </div>
        </div>
      );
  }

  // Main List View
  return (
    <div className="space-y-6 animate-[fadeIn_0.3s_ease-out]">
        <div className="flex items-center justify-between pb-4 border-b border-slate-800">
            <div>
                <h3 className="text-lg font-medium text-white mb-1">Configuration Profiles ({profiles.length})</h3>
                <p className="text-sm text-slate-500">Manage API setups. Active profile is used for chat.</p>
            </div>
            <button 
                onClick={onCreateNew}
                className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-medium transition-colors shadow-lg shadow-indigo-500/20"
            >
                <PlusCircle size={16} /> New Config
            </button>
        </div>

        <div className="grid grid-cols-1 gap-3">
            {profiles.map(p => {
                const isActive = p.id === activeProfileId;
                const isDeleting = deleteConfirmationId === p.id;
                
                let activeBorder = 'border-indigo-500/50';
                let activeBg = 'bg-indigo-600';
                if (p.providerId.includes('deepseek')) { activeBorder = 'border-blue-500/50'; activeBg = 'bg-blue-600'; }
                else if (p.providerId.includes('tongyi')) { activeBorder = 'border-purple-500/50'; activeBg = 'bg-purple-600'; }
                else if (p.providerId.includes('openai')) { activeBorder = 'border-emerald-500/50'; activeBg = 'bg-emerald-600'; }
                else if (p.providerId.includes('google')) { activeBorder = 'border-orange-500/50'; activeBg = 'bg-orange-600'; }

                return (
                    <div key={p.id} className={`p-4 rounded-xl border flex items-center justify-between group transition-all ${
                        isActive 
                        ? `bg-slate-900 border ${activeBorder} shadow-[0_0_15px_rgba(0,0,0,0.3)]` 
                        : `bg-slate-900/40 border-slate-800 hover:border-slate-700`
                    }`}>
                        <div className="flex items-center gap-4">
                            <div className={`p-3 rounded-xl shrink-0 ${isActive ? `${activeBg} text-white` : 'bg-slate-800 text-slate-500'}`}>
                                {getProviderIcon(p.providerId)}
                            </div>
                            <div>
                                <div className="flex items-center gap-2 mb-1">
                                    <h4 className="font-medium text-slate-200">{p.name}</h4>
                                    {isActive && <span className={`text-[10px] ${isActive ? 'text-white/80' : 'text-slate-500'} px-1.5 py-0.5 rounded border border-white/20 font-bold`}>Active</span>}
                                </div>
                                <div className="text-xs text-slate-500 flex flex-col gap-1">
                                    <span className="flex items-center gap-2">
                                        <span className={`font-mono px-1.5 py-0.5 rounded bg-slate-800/50 text-slate-400`}>
                                            {p.providerId}
                                        </span>
                                        <span className="text-slate-600">•</span>
                                        <span className="font-mono text-slate-500">
                                            {p.apiKey ? `...${p.apiKey.slice(-4)}` : 'No Key'}
                                        </span>
                                    </span>
                                    <span className="flex items-center gap-1.5 text-slate-400">
                                        <Layers size={10} />
                                        {p.cachedModelCount !== undefined ? (
                                            <span>{p.cachedModelCount} Models Available</span>
                                        ) : (
                                            <span className="italic opacity-50">Unknown Model Count</span>
                                        )}
                                    </span>
                                </div>
                            </div>
                        </div>
                        
                        <div className="flex items-center gap-2">
                            {isDeleting ? (
                                <div className="flex items-center bg-red-900/20 border border-red-900/50 rounded-lg p-1 animate-[fadeIn_0.2s_ease-out]">
                                    <span className="text-xs text-red-300 font-medium px-2">Delete?</span>
                                    <button 
                                        onClick={() => { onDeleteProfile(p.id); setDeleteConfirmationId(null); }}
                                        className="px-2 py-1 bg-red-600 hover:bg-red-500 text-white rounded text-xs mr-1 transition-colors"
                                    >
                                        Yes
                                    </button>
                                    <button 
                                        onClick={() => setDeleteConfirmationId(null)}
                                        className="px-2 py-1 bg-slate-700 hover:bg-slate-600 text-slate-200 rounded text-xs transition-colors"
                                    >
                                        No
                                    </button>
                                </div>
                            ) : (
                                <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                    <button 
                                        onClick={() => handleInspectProfile(p)}
                                        className="p-2 bg-slate-800 hover:bg-slate-700 hover:text-white text-slate-400 rounded-lg transition-colors border border-slate-700"
                                        title="View Available Models"
                                    >
                                        <List size={16} />
                                    </button>
                                    {!isActive && (
                                        <button 
                                            onClick={() => onActivateProfile(p.id)}
                                            className="p-2 bg-slate-800 hover:bg-green-600 hover:text-white text-slate-400 rounded-lg transition-colors border border-slate-700"
                                            title="Activate"
                                        >
                                            <Check size={16} />
                                        </button>
                                    )}
                                    <button 
                                        onClick={() => handleDuplicate(p)}
                                        className="p-2 bg-slate-800 hover:bg-slate-600 hover:text-white text-slate-400 rounded-lg transition-colors border border-slate-700"
                                        title="Duplicate"
                                    >
                                        <Copy size={16} />
                                    </button>
                                    <button 
                                        onClick={() => onEditProfile(p)}
                                        className="p-2 bg-slate-800 hover:bg-blue-600 hover:text-white text-slate-400 rounded-lg transition-colors border border-slate-700"
                                        title="Edit"
                                    >
                                        <Edit3 size={16} />
                                    </button>
                                    <button 
                                        onClick={() => setDeleteConfirmationId(p.id)}
                                        className="p-2 bg-slate-800 hover:bg-red-600 hover:text-white text-slate-400 rounded-lg transition-colors border border-slate-700"
                                        title="Delete"
                                    >
                                        <Trash2 size={16} />
                                    </button>
                                </div>
                            )}
                        </div>
                    </div>
                );
            })}
            {profiles.length === 0 && (
                <div className="text-center py-10 text-slate-500 italic">No saved profiles. Create one to get started.</div>
            )}
        </div>
    </div>
  );
};
