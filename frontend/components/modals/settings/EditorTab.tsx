
import React, { useState, useEffect } from 'react';
import { Save, Key, Shield, RefreshCw, CheckCircle2, AlertTriangle, Check, Loader2 } from 'lucide-react';
import { ConfigProfile } from '../../../services/db';
import { ModelConfig, ApiProtocol } from '../../../../types';
import { STATIC_AI_PROVIDERS } from '../../../config/aiProviders';
import { LLMFactory } from '../../../services/LLMFactory';
import { v4 as uuidv4 } from 'uuid';

interface EditorTabProps {
  initialData?: ConfigProfile | null;
  existingProfiles: ConfigProfile[];
  onSave: (profile: ConfigProfile) => Promise<void>;
  onClose: () => void;
}

export const EditorTab: React.FC<EditorTabProps> = ({
  initialData,
  existingProfiles,
  onSave,
  onClose
}) => {
  const [formData, setFormData] = useState<ConfigProfile | null>(null);
  
  // Verification State
  const [verifiedModels, setVerifiedModels] = useState<ModelConfig[]>([]);
  const [isVerifying, setIsVerifying] = useState(false);
  const [verifyError, setVerifyError] = useState<string | null>(null);

  // Initialize Form
  useEffect(() => {
      if (initialData) {
          setFormData({ ...initialData });
          if (initialData.savedModels && initialData.savedModels.length > 0) {
              setVerifiedModels(initialData.savedModels);
          } else {
              setVerifiedModels([]);
          }
      } else {
          // New Profile
          setFormData({
              id: uuidv4(),
              name: 'New Configuration',
              providerId: 'google',
              apiKey: '',
              baseUrl: 'https://generativelanguage.googleapis.com',
              protocol: 'google',
              isProxy: false,
              hiddenModels: [],
              cachedModelCount: 0,
              savedModels: [],
              createdAt: Date.now(),
              updatedAt: Date.now()
          });
          setVerifiedModels([]);
      }
      setVerifyError(null);
  }, [initialData]);

  const handleVerify = async () => {
      if (!formData) return;
      setIsVerifying(true);
      setVerifiedModels([]);
      setVerifyError(null);
      
      try {
          const providerInstance = LLMFactory.getProvider(formData.protocol as ApiProtocol, formData.providerId);
          const models = await providerInstance.getAvailableModels(formData.apiKey, formData.baseUrl);
          
          if (models.length > 0) {
              setVerifiedModels(models);
              
              setFormData(prev => {
                  if (!prev) return null;

                  // Smart Selection for Fresh Setup
                  let nextHidden = prev.hiddenModels;
                  if (prev.cachedModelCount === 0) {
                      const staticConfig = STATIC_AI_PROVIDERS.find(p => p.id === prev.providerId);
                      const defaultModelId = staticConfig?.defaultModel;
                      
                      const visibleModel = (defaultModelId && models.find(m => m.id === defaultModelId))
                          || models.find(m => m.id.toLowerCase().includes('chat')) 
                          || models[0];
                      
                      nextHidden = models.filter(m => m.id !== visibleModel.id).map(m => m.id);
                  }

                  return { 
                      ...prev, 
                      cachedModelCount: models.length,
                      savedModels: models,
                      hiddenModels: nextHidden
                  };
              });
          } else {
              setVerifyError("Connection established, but no models were returned.");
          }
      } catch (e: any) {
          setVerifyError(e.message || "Connection failed.");
      } finally {
          setIsVerifying(false);
      }
  };

  const handleSaveInternal = async () => {
      if (!formData) return;
      if (!formData.name.trim()) {
          alert("Please enter a configuration name.");
          return;
      }

      const profileToSave: ConfigProfile = {
          ...formData,
          updatedAt: Date.now(),
          savedModels: verifiedModels.length > 0 ? verifiedModels : formData.savedModels,
          cachedModelCount: verifiedModels.length > 0 ? verifiedModels.length : formData.cachedModelCount
      };

      await onSave(profileToSave);
  };

  const toggleEditorModelVisibility = (id: string) => {
      if (!formData) return;
      const currentHidden = new Set(formData.hiddenModels);
      if (currentHidden.has(id)) currentHidden.delete(id);
      else currentHidden.add(id);
      
      setFormData({
          ...formData,
          hiddenModels: Array.from(currentHidden)
      });
  };

  if (!formData) {
      return (
          <div className="flex flex-col items-center justify-center h-48 text-slate-500">
              <Loader2 size={24} className="animate-spin text-indigo-500 mb-2" />
              <p>Initializing Editor...</p>
          </div>
      );
  }

  return (
    <>
    <div className="space-y-8 animate-[fadeIn_0.3s_ease-out]">
        
        <div className="pb-4 border-b border-slate-800 flex justify-between items-center">
            <div>
                <h3 className="text-lg font-medium text-white mb-1">
                    {initialData ? 'Edit Configuration' : 'New Configuration'}
                </h3>
                <p className="text-sm text-slate-500">Configure connection details.</p>
            </div>
            <div className="text-xs font-mono text-slate-600 bg-slate-900 px-2 py-1 rounded">
                ID: {formData.id.slice(0, 8)}...
            </div>
        </div>

        <div className="space-y-6">
            
            {/* Name Input */}
            <div className="space-y-2">
                <label className="text-xs font-medium text-slate-400">Configuration Name</label>
                <input 
                    type="text"
                    value={formData.name}
                    onChange={e => setFormData({...formData, name: e.target.value})}
                    placeholder="e.g. Work OpenAI"
                    className="w-full bg-slate-950 border border-slate-700 rounded-lg px-4 py-3 text-sm focus:border-indigo-500 outline-none text-slate-200"
                />
            </div>

            {/* Template Selection */}
            <div className="space-y-2">
                <div className="flex justify-between items-center">
                    <label className="text-xs font-medium text-slate-400">Provider Template</label>
                    <span className="text-[10px] text-slate-600">Clicking applies default settings</span>
                </div>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    {STATIC_AI_PROVIDERS.map(p => (
                        <button
                            key={p.id}
                            onClick={() => {
                                setFormData(prev => {
                                    if (!prev) return null;
                                    return {
                                        ...prev,
                                        providerId: p.id,
                                        protocol: p.protocol,
                                        baseUrl: p.isCustom ? prev.baseUrl : p.baseUrl,
                                        isProxy: !!p.isCustom,
                                        name: (prev.name === 'New Configuration' || prev.name.includes('Config')) ? `${p.name} Config` : prev.name
                                    };
                                });
                                setVerifiedModels([]); 
                            }}
                            className={`flex items-center gap-2 p-3 rounded-xl border text-left transition-all ${
                                formData.providerId === p.id 
                                ? 'bg-indigo-600/10 border-indigo-500 ring-1 ring-indigo-500/50 text-indigo-200' 
                                : 'bg-slate-900 border-slate-800 hover:bg-slate-800 text-slate-400'
                            }`}
                        >
                            <div className={`w-2 h-2 rounded-full ${formData.providerId === p.id ? 'bg-indigo-500' : 'bg-slate-600'}`} />
                            <span className="text-sm font-medium">{p.name}</span>
                        </button>
                    ))}
                </div>
            </div>

            {/* Connection Details Box */}
            <div className="bg-slate-900/30 p-5 rounded-xl border border-slate-800/50 space-y-5">
                <div className="flex items-center justify-between">
                    <h4 className="text-sm font-medium text-slate-200 flex items-center gap-2">
                        <Key size={14} className="text-indigo-400" /> Connection Details
                    </h4>
                    <div className="flex bg-slate-800 p-1 rounded-lg border border-slate-700">
                        <button 
                            onClick={() => setFormData({...formData, isProxy: false})}
                            className={`px-3 py-1 text-xs font-medium rounded-md transition-all ${!formData.isProxy ? 'bg-indigo-600 text-white' : 'text-slate-400'}`}
                        >Standard</button>
                        <button 
                            onClick={() => setFormData({...formData, isProxy: true})}
                            className={`px-3 py-1 text-xs font-medium rounded-md transition-all ${formData.isProxy ? 'bg-indigo-600 text-white' : 'text-slate-400'}`}
                        >Custom / Proxy</button>
                    </div>
                </div>

                <div className="space-y-4">
                    <div className="space-y-2">
                        <label className="text-xs font-medium text-slate-400">API Endpoint (Base URL)</label>
                        {formData.isProxy ? (
                            <input 
                                type="text"
                                value={formData.baseUrl}
                                onChange={e => setFormData({...formData, baseUrl: e.target.value})}
                                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-4 py-3 text-sm focus:border-indigo-500 outline-none text-slate-200 font-mono"
                                placeholder="https://api.custom.com/v1"
                            />
                        ) : (
                            <div className="w-full bg-slate-900/50 border border-slate-800 rounded-lg px-4 py-3 text-sm text-slate-500 font-mono select-none cursor-not-allowed">
                                {formData.baseUrl || 'Default'}
                            </div>
                        )}
                    </div>

                    <div className="space-y-2">
                        <label className="text-xs font-medium text-slate-400">API Key</label>
                        <div className="relative">
                            <input 
                                type="password"
                                value={formData.apiKey}
                                onChange={e => setFormData({...formData, apiKey: e.target.value})}
                                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-4 py-3 text-sm focus:border-indigo-500 outline-none text-slate-200 pr-10 font-mono"
                                placeholder="sk-..."
                                autoComplete="off"
                            />
                            <Shield size={14} className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-600" />
                        </div>
                    </div>

                    <div className="flex justify-end pt-2">
                        <button
                            type="button"
                            onClick={handleVerify}
                            disabled={isVerifying || !formData.apiKey}
                            className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-medium transition-colors border border-slate-700"
                        >
                            <RefreshCw size={14} className={isVerifying ? 'animate-spin' : ''} />
                            {isVerifying ? 'Verifying...' : 'Verify Connection & List Models'}
                        </button>
                    </div>
                </div>
            </div>

            {/* Models List (Verification Result) */}
            {(verifiedModels.length > 0 || verifyError) && (
                <div className="animate-[fadeIn_0.3s_ease-out]">
                    {verifyError ? (
                        <div className="p-4 bg-red-900/20 border border-red-900/50 rounded-xl text-red-300 text-sm flex items-start gap-3">
                            <AlertTriangle size={18} className="shrink-0 mt-0.5" />
                            <div>
                                <div className="font-bold mb-1">Verification Failed</div>
                                <div className="opacity-80">{verifyError}</div>
                            </div>
                        </div>
                    ) : (
                        <div className="bg-slate-900/30 rounded-xl border border-slate-800 overflow-hidden">
                            <div className="p-3 bg-slate-900/50 border-b border-slate-800 flex items-center justify-between">
                                <div className="flex items-center gap-2 text-green-400">
                                    <CheckCircle2 size={16} />
                                    <span className="text-sm font-medium">Connection Verified</span>
                                </div>
                                <div className="flex items-center gap-2">
                                    <button 
                                        onClick={() => setFormData(prev => prev ? ({...prev, hiddenModels: []}) : null)}
                                        className="text-[10px] bg-slate-800 hover:bg-slate-700 px-2 py-1 rounded text-slate-300 transition-colors"
                                    >
                                        All
                                    </button>
                                    <button 
                                        onClick={() => setFormData(prev => prev ? ({...prev, hiddenModels: verifiedModels.map(m => m.id)}) : null)}
                                        className="text-[10px] bg-slate-800 hover:bg-slate-700 px-2 py-1 rounded text-slate-300 transition-colors"
                                    >
                                        None
                                    </button>
                                    <span className="text-xs text-slate-500 ml-1 border-l border-slate-700 pl-2">{verifiedModels.length} Models</span>
                                </div>
                            </div>
                            <div className="overflow-y-auto p-2 custom-scrollbar">
                                <div className="text-xs text-slate-500 px-2 py-1 mb-2">
                                    Select models to show in the dropdown. Unchecked models will be hidden.
                                </div>
                                <div className="grid grid-cols-1 md:grid-cols-4 gap-1">
                                    {verifiedModels.map(model => {
                                        const isHidden = formData.hiddenModels.includes(model.id);
                                        return (
                                            <label key={model.id} className={`flex items-center gap-3 p-2 rounded-lg cursor-pointer transition-colors ${!isHidden ? 'bg-slate-800/50 hover:bg-slate-800' : 'opacity-50 hover:opacity-80 hover:bg-slate-800/30'}`}>
                                                <div 
                                                    className={`w-4 h-4 rounded border flex items-center justify-center transition-colors ${
                                                        !isHidden ? 'bg-indigo-600 border-indigo-600 text-white' : 'border-slate-600 bg-transparent'
                                                    }`}
                                                    onClick={(e) => {
                                                        e.preventDefault();
                                                        toggleEditorModelVisibility(model.id);
                                                    }}
                                                >
                                                    {!isHidden && <Check size={12} />}
                                                </div>
                                                <div className="min-w-0">
                                                    <div className={`text-xs font-medium truncate ${!isHidden ? 'text-slate-200' : 'text-slate-500'}`}>
                                                        {model.name}
                                                    </div>
                                                    <div className="text-xs text-slate-600 font-mono truncate">
                                                        {model.id}
                                                    </div>
                                                </div>
                                            </label>
                                        );
                                    })}
                                </div>
                            </div>
                        </div>
                    )}
                </div>
            )}

        </div>
    </div>

    {/* Footer Portal would go here, but since this is a subcomponent, we rely on Parent or local layout */}
    <div className="p-6 border-t border-slate-800 bg-slate-900 flex justify-end gap-3 z-10 sticky bottom-0 -mx-4 -mb-4 mt-8">
       <button 
          onClick={onClose}
          className="px-5 py-2.5 rounded-xl text-slate-400 hover:text-white hover:bg-slate-900 transition-colors text-sm font-medium"
       >
           Close
       </button>
       <button 
          onClick={handleSaveInternal}
          className="px-6 py-2.5 rounded-xl bg-gradient-to-r from-indigo-600 to-blue-600 hover:from-indigo-500 hover:to-blue-500 text-white shadow-lg shadow-indigo-500/20 transition-all text-sm font-medium flex items-center gap-2"
       >
           <Save size={16} /> Save Configuration
       </button>
    </div>
    </>
  );
};
