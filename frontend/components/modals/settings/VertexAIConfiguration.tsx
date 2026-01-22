import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { Save, Loader2, X, Image as ImageIcon, RefreshCw, CheckCircle2, AlertTriangle, Check, Eye, Search, Brain, Code } from 'lucide-react';
import { db } from '../../../services/db';
import { 
    ImagenAPISettings, 
    ImagenConfigResponse
} from '../../../types/imagen-config';
import { ModelConfig } from '../../../types/types';
import { useToastContext } from '../../../contexts/ToastContext';

interface VertexAIConfigurationProps {
    footerNode?: HTMLDivElement | null;
    onClose: () => void;
}

interface VertexAIModel {
    id: string;
    name: string;
    displayName?: string;
    description?: string;
    capabilities?: {
        vision: boolean;
        search: boolean;
        reasoning: boolean;
        coding: boolean;
    };
}

interface VerifyVertexAIResponse {
    success: boolean;
    message: string;
    models: VertexAIModel[];
}

export const VertexAIConfiguration: React.FC<VertexAIConfigurationProps> = ({
    footerNode,
    onClose
}) => {
    const [imagenConfig, setImagenConfig] = useState<ImagenAPISettings | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [isSaving, setIsSaving] = useState(false);
    const { showSuccess, showError } = useToastContext();
    
    // Verification State
    const [verifiedModels, setVerifiedModels] = useState<VertexAIModel[]>([]);
    const [isVerifying, setIsVerifying] = useState(false);
    const [verifyError, setVerifyError] = useState<string | null>(null);
    const [selectedModels, setSelectedModels] = useState<Set<string>>(new Set());

    // Load Imagen configuration
    useEffect(() => {
        const loadImagenConfig = async () => {
            try {
                setIsLoading(true);
                
                // 编辑模式：传递 edit_mode=true 以获取解密后的凭证
                const data = await db.request<ImagenConfigResponse>('/vertex-ai/config?edit_mode=true');
                
                // Initialize Vertex AI configuration from API response
                setImagenConfig({
                    apiMode: data.apiMode || 'vertex_ai',
                    geminiApiKey: '',
                    vertexAI: {
                        projectId: data.vertexAiProjectId || '',
                        location: data.vertexAiLocation || 'us-central1',
                        credentialsJson: data.vertexAiCredentialsJson || ''
                    }
                });
                
                // Restore saved models and display them if available
                if (data.savedModels && data.savedModels.length > 0) {
                    // Convert ModelConfig[] to VertexAIModel[]
                    // ✅ 保留 capabilities 和 description 信息
                    const savedModelList: VertexAIModel[] = data.savedModels.map((sm: ModelConfig) => ({
                        id: sm.id,
                        name: sm.name || sm.id,
                        displayName: sm.name || sm.id,
                        description: sm.description,  // ✅ 保留描述
                        capabilities: sm.capabilities || {
                            vision: false,
                            search: false,
                            reasoning: false,
                            coding: false
                        }
                    }));
                    
                    // Also include hidden models in the display (but unselected)
                    const allModelsMap = new Map<string, VertexAIModel>();
                    savedModelList.forEach(m => allModelsMap.set(m.id, m));
                    
                    // Add hidden models to the list (if any)
                    if (data.hiddenModels && data.hiddenModels.length > 0) {
                        data.hiddenModels.forEach((hmId: string) => {
                            if (!allModelsMap.has(hmId)) {
                                allModelsMap.set(hmId, {
                                    id: hmId,
                                    name: hmId,
                                    displayName: hmId
                                });
                            }
                        });
                    }
                    
                    setVerifiedModels(Array.from(allModelsMap.values()));
                    
                    // Restore selected models (only saved models are selected, hidden models are not)
                    setSelectedModels(new Set(data.savedModels.map((sm: ModelConfig) => sm.id)));
                }
            } catch (error: any) {
                console.error('[VertexAIConfiguration] Failed to load Imagen configuration:', error);
                setImagenConfig({
                    apiMode: 'vertex_ai',
                    geminiApiKey: '',
                    vertexAI: {
                        projectId: '',
                        location: 'us-central1',
                        credentialsJson: ''
                    }
                });
            } finally {
                setIsLoading(false);
            }
        };

        loadImagenConfig();
    }, []);

    const handleVerify = async () => {
        if (!imagenConfig?.vertexAI) return;
        
        const { projectId, location, credentialsJson } = imagenConfig.vertexAI;
        
        if (!projectId || !credentialsJson) {
            setVerifyError('Please fill in Project ID and Service Account JSON');
            return;
        }
        
        setIsVerifying(true);
        setVerifiedModels([]);
        setVerifyError(null);

        try {
            const response = await db.request<VerifyVertexAIResponse>('/vertex-ai/verify-vertex-ai', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    projectId,
                    location: location || 'us-central1',
                    credentialsJson
                })
            });

            if (response.success && response.models.length > 0) {
                // Process models: extract short names and filter duplicates
                const processedModels = response.models.map(m => {
                    // Extract short name from full path
                    // e.g., "publishers/google/models/gemini-3-pro-image-preview" -> "gemini-3-pro-image-preview"
                    const shortId = m.id.includes('/') ? m.id.split('/').pop() || m.id : m.id;
                    const shortName = m.name.includes('/') ? m.name.split('/').pop() || m.name : m.name;
                    
                    return {
                        id: shortId,
                        name: shortName,
                        displayName: m.displayName || shortName,
                        description: m.description,  // ✅ 保留后端返回的描述
                        capabilities: m.capabilities || {
                            vision: false,
                            search: false,
                            reasoning: false,
                            coding: false
                        }
                    };
                });
                
                // Remove duplicates based on id
                const uniqueModels = Array.from(
                    new Map(processedModels.map(m => [m.id, m])).values()
                );
                
                setVerifiedModels(uniqueModels);
                
                // ✅ Verify Connection 时，不使用数据库中的旧模型列表
                // 只恢复已保存的模型选择状态（哪些模型被选中），但使用最新获取的模型数据
                // 这样可以确保显示的是最新的模型列表，而不是数据库中的旧数据
                try {
                    // 编辑模式：传递 edit_mode=true 以获取解密后的凭证
                    const configData = await db.request<ImagenConfigResponse>('/vertex-ai/config?edit_mode=true');
                    if (configData.savedModels && configData.savedModels.length > 0) {
                        // 只恢复选中状态，使用最新获取的模型数据
                        const savedModelIds = configData.savedModels.map((sm: ModelConfig) => sm.id);
                        const validSavedModels = savedModelIds.filter(id => 
                            uniqueModels.some(m => m.id === id)
                        );
                        
                        if (validSavedModels.length > 0) {
                            setSelectedModels(new Set(validSavedModels));
                            return; // Exit early if we restored selection from saved models
                        }
                    }
                } catch (e) {
                    console.warn('[VertexAIConfiguration] Failed to load saved config during verification:', e);
                }
                
                // Fallback: use current selection or auto-select image-related models
                const currentSelected = Array.from(selectedModels);
                const validSavedModels = currentSelected.filter(id => 
                    uniqueModels.some(m => m.id === id)
                );
                
                if (validSavedModels.length > 0) {
                    // Keep existing selection if valid
                    setSelectedModels(new Set(validSavedModels));
                } else {
                    // Auto-select image-related models if no valid saved selection
                    const imageModels = uniqueModels.filter(m => 
                        m.id.toLowerCase().includes('image') || 
                        m.id.toLowerCase().includes('imagen') ||
                        m.id.toLowerCase().includes('veo')
                    );
                    setSelectedModels(new Set(imageModels.map(m => m.id)));
                }
            } else {
                setVerifyError(response.message || "Connection established, but no models were returned.");
            }
        } catch (e: any) {
            console.error('[VertexAIConfiguration] Verification failed:', e);
            setVerifyError(e.message || "Connection failed.");
        } finally {
            setIsVerifying(false);
        }
    };

    const toggleModelSelection = (modelId: string) => {
        const newSelected = new Set(selectedModels);
        if (newSelected.has(modelId)) {
            newSelected.delete(modelId);
        } else {
            newSelected.add(modelId);
        }
        setSelectedModels(newSelected);
    };

    const handleSave = async () => {
        if (!imagenConfig) return;

        try {
            setIsSaving(true);
            
            // Convert selected models to ModelConfig format
            // ✅ 使用从后端返回的 capabilities 和 description，而不是全部 false 或和 name 一样
            const selectedModelConfigs: ModelConfig[] = verifiedModels
                .filter(m => selectedModels.has(m.id))
                .map(m => ({
                    id: m.id,
                    name: m.displayName || m.name || m.id,
                    description: m.description || m.displayName || m.name || m.id,  // ✅ 优先使用后端返回的描述
                    capabilities: m.capabilities || {
                        vision: false,
                        search: false,
                        reasoning: false,
                        coding: false
                    },
                    contextWindow: 0
                }));
            
            // Calculate hidden models: all verified models that are NOT selected
            const hiddenModelIds = verifiedModels
                .filter(m => !selectedModels.has(m.id))
                .map(m => m.id);
            
            const requestBody = {
                apiMode: 'vertex_ai',
                vertexAiProjectId: imagenConfig.vertexAI?.projectId,
                vertexAiLocation: imagenConfig.vertexAI?.location || 'us-central1',
                vertexAiCredentialsJson: imagenConfig.vertexAI?.credentialsJson,
                hiddenModels: hiddenModelIds,  // Save hidden models (unselected models)
                savedModels: selectedModelConfigs  // Save selected models as ModelConfig[]
            };

            await db.request('/vertex-ai/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(requestBody)
            });

            showSuccess('Vertex AI configuration saved successfully!');
            onClose();
        } catch (error: any) {
            console.error('[VertexAIConfiguration] Failed to save Vertex AI configuration:', error);
            showError(`Failed to save Vertex AI configuration: ${error.message}`);
        } finally {
            setIsSaving(false);
        }
    };

    if (isLoading || !imagenConfig) {
        return (
            <div className="flex flex-col items-center justify-center h-full text-slate-500">
                <Loader2 size={24} className="animate-spin text-indigo-500 mb-2" />
                <p>Loading Imagen configuration...</p>
            </div>
        );
    }

    return (
        <>
            <div className="absolute inset-0 flex flex-col p-3 md:p-4 space-y-2 md:space-y-3 animate-[fadeIn_0.3s_ease-out]">

                <div className="border-b border-slate-800 pb-3 shrink-0">
                    <div className="flex items-center gap-3 mb-2">
                        <ImageIcon size={24} className="text-indigo-400" />
                        <h3 className="text-lg md:text-xl font-medium text-white">
                            Vertex AI Configuration
                        </h3>
                    </div>
                    <p className="text-xs text-slate-500">
                        Configure Vertex AI for image generation with Google Gemini
                    </p>
                </div>

                <div className="flex-1 flex flex-col min-h-0 space-y-2 md:space-y-3 overflow-y-auto custom-scrollbar pr-1 pb-24">

                    {/* Vertex AI Configuration */}
                    <div className="bg-slate-900/30 p-4 rounded-xl border border-slate-800/50 space-y-4 shrink-0">
                        <h4 className="text-sm font-bold uppercase tracking-wider text-slate-400">
                            Vertex AI Settings
                        </h4>

                        <div className="space-y-1.5">
                            <label className="text-xs font-medium text-slate-500">Project ID</label>
                            <input
                                type="text"
                                value={imagenConfig.vertexAI?.projectId || ''}
                                onChange={e => setImagenConfig({
                                    ...imagenConfig,
                                    vertexAI: {
                                        projectId: e.target.value,
                                        location: imagenConfig.vertexAI?.location || 'us-central1',
                                        credentialsJson: imagenConfig.vertexAI?.credentialsJson || ''
                                    }
                                })}
                                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:border-indigo-500 outline-none text-slate-200"
                                placeholder="my-project-123"
                            />
                        </div>

                        <div className="space-y-1.5">
                            <label className="text-xs font-medium text-slate-500">Location</label>
                            <input
                                type="text"
                                value={imagenConfig.vertexAI?.location || 'us-central1'}
                                onChange={e => setImagenConfig({
                                    ...imagenConfig,
                                    vertexAI: {
                                        projectId: imagenConfig.vertexAI?.projectId || '',
                                        location: e.target.value,
                                        credentialsJson: imagenConfig.vertexAI?.credentialsJson || ''
                                    }
                                })}
                                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:border-indigo-500 outline-none text-slate-200"
                                placeholder="us-central1"
                            />
                        </div>

                        <div className="space-y-1.5">
                            <label className="text-xs font-medium text-slate-500">Service Account JSON</label>
                            <textarea
                                value={imagenConfig.vertexAI?.credentialsJson || ''}
                                onChange={e => setImagenConfig({
                                    ...imagenConfig,
                                    vertexAI: {
                                        projectId: imagenConfig.vertexAI?.projectId || '',
                                        location: imagenConfig.vertexAI?.location || 'us-central1',
                                        credentialsJson: e.target.value
                                    }
                                })}
                                className="w-full bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-sm focus:border-indigo-500 outline-none text-slate-200 font-mono resize-y"
                                placeholder='{"type": "service_account", "project_id": "...", ...}'
                                rows={10}
                            />
                            <p className="text-xs text-slate-600">
                                Paste the complete JSON content from your service account key file
                            </p>
                        </div>

                        <div className="flex justify-end">
                            <button
                                type="button"
                                onClick={handleVerify}
                                disabled={isVerifying || !imagenConfig.vertexAI?.projectId || !imagenConfig.vertexAI?.credentialsJson}
                                className="flex items-center gap-2 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs font-medium transition-colors border border-slate-700 shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                <RefreshCw size={12} className={isVerifying ? 'animate-spin' : ''} />
                                {isVerifying ? 'Verifying...' : 'Verify Connection'}
                            </button>
                        </div>
                    </div>

                    {/* Models List (Verification Result) */}
                    {(verifiedModels.length > 0 || verifyError) && (
                        <div className="animate-[fadeIn_0.3s_ease-out] flex flex-col">
                            {verifyError ? (
                                <div className="p-3 bg-red-900/20 border border-red-900/50 rounded-xl text-red-300 text-xs flex items-start gap-3 shrink-0">
                                    <AlertTriangle size={16} className="shrink-0 mt-0.5" />
                                    <div>
                                        <div className="font-bold mb-0.5">Verification Failed</div>
                                        <div className="opacity-80">{verifyError}</div>
                                    </div>
                                </div>
                            ) : (
                                <div className="bg-slate-900/30 rounded-xl border border-slate-800 flex flex-col mt-2">
                                    <div className="p-2 bg-slate-900/50 border-b border-slate-800 flex items-center justify-between shrink-0">
                                        <div className="flex items-center gap-2 text-green-400 px-1">
                                            <CheckCircle2 size={14} />
                                            <span className="text-xs font-medium">Verified</span>
                                        </div>
                                        <div className="flex items-center gap-2 md:gap-1.5 flex-wrap">
                                            <button
                                                onClick={() => setSelectedModels(new Set(verifiedModels.map(m => m.id)))}
                                                className="text-xs bg-slate-800 hover:bg-slate-700 px-3 py-1.5 md:px-2 md:py-0.5 rounded text-slate-300 transition-colors border border-slate-700"
                                            >
                                                Select All
                                            </button>
                                            <button
                                                onClick={() => setSelectedModels(new Set())}
                                                className="text-xs bg-slate-800 hover:bg-slate-700 px-3 py-1.5 md:px-2 md:py-0.5 rounded text-slate-300 transition-colors border border-slate-700"
                                            >
                                                Select None
                                            </button>
                                            <span className="text-xs text-slate-500 ml-1 border-l border-slate-700 pl-2">{verifiedModels.length} Models</span>
                                        </div>
                                    </div>

                                    <div className="bg-slate-950/30 p-2 text-xs text-slate-500 border-b border-slate-800/50 shrink-0">
                                        Available models in your Vertex AI project. Image-related models are pre-selected.
                                    </div>

                                    <div className="w-full p-3 md:p-2 max-h-96 overflow-y-auto">
                                        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2 md:gap-1 w-full">
                                            {verifiedModels.map(model => {
                                                const isSelected = selectedModels.has(model.id);
                                                const isImageModel = model.id.toLowerCase().includes('image') || 
                                                                     model.id.toLowerCase().includes('imagen') ||
                                                                     model.id.toLowerCase().includes('veo');
                                                
                                                return (
                                                    <div
                                                        key={model.id}
                                                        onClick={() => toggleModelSelection(model.id)}
                                                        className={`flex items-center gap-2 p-2 md:p-1.5 rounded-md cursor-pointer transition-colors border ${
                                                            isSelected 
                                                                ? 'bg-slate-800/60 border-slate-700/50 hover:bg-slate-800' 
                                                                : 'opacity-60 border-transparent hover:bg-slate-800/20'
                                                        }`}
                                                    >
                                                        <div
                                                            className={`w-3.5 h-3.5 rounded-[3px] border flex items-center justify-center transition-colors shrink-0 ${
                                                                isSelected 
                                                                    ? 'bg-indigo-600 border-indigo-600 text-white' 
                                                                    : 'border-slate-600 bg-transparent'
                                                            }`}
                                                        >
                                                            {isSelected && <Check size={10} />}
                                                        </div>
                                                        <div className="min-w-0 flex-1 overflow-hidden">
                                                            <div className={`text-xs md:text-[11px] font-medium truncate leading-tight flex items-center gap-1 ${
                                                                isSelected ? 'text-slate-200' : 'text-slate-500'
                                                            }`}>
                                                                {model.id}
                                                                {isImageModel && (
                                                                    <ImageIcon size={10} className="text-indigo-400 shrink-0" />
                                                                )}
                                                            </div>
                                                            {/* ✅ 显示描述（如果存在且与ID不同，且不包含ID的主要部分） */}
                                                            {(() => {
                                                                if (!model.description || model.description === model.id) {
                                                                    return null;
                                                                }
                                                                // 检查描述是否包含ID的主要关键词（避免重复显示）
                                                                const idWords = model.id.toLowerCase().split(/[-_\s]+/).filter(w => w.length > 2);
                                                                const descLower = model.description.toLowerCase();
                                                                const hasMajorOverlap = idWords.some(word => descLower.includes(word));
                                                                // 如果描述包含ID的主要部分，则不显示描述
                                                                if (hasMajorOverlap && idWords.length > 2) {
                                                                    return null;
                                                                }
                                                                return (
                                                                    <div className="text-[10px] text-slate-500 truncate leading-tight mt-0.5 opacity-80">
                                                                        {model.description}
                                                                    </div>
                                                                );
                                                            })()}
                                                            <div className="flex items-center gap-1.5 mt-0.5">
                                                                {/* 能力图标 */}
                                                                {model.capabilities && (
                                                                    <div className="flex items-center gap-1 shrink-0">
                                                                        {model.capabilities.vision && (
                                                                            <div title="Vision">
                                                                                <Eye size={9} className="text-blue-400" />
                                                                            </div>
                                                                        )}
                                                                        {model.capabilities.search && (
                                                                            <div title="Search">
                                                                                <Search size={9} className="text-green-400" />
                                                                            </div>
                                                                        )}
                                                                        {model.capabilities.reasoning && (
                                                                            <div title="Reasoning">
                                                                                <Brain size={9} className="text-purple-400" />
                                                                            </div>
                                                                        )}
                                                                        {model.capabilities.coding && (
                                                                            <div title="Coding">
                                                                                <Code size={9} className="text-orange-400" />
                                                                            </div>
                                                                        )}
                                                                    </div>
                                                                )}
                                                            </div>
                                                        </div>
                                                    </div>
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

            {/* Footer Portal */}
            {footerNode && createPortal(
                <>
                    <button
                        onClick={onClose}
                        className="px-4 py-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors text-xs font-medium flex items-center gap-1"
                    >
                        <X size={16} /> Close
                    </button>
                    <button
                        onClick={handleSave}
                        disabled={isSaving}
                        className="px-5 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-500/20 transition-all text-sm font-medium flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        {isSaving ? (
                            <>
                                <Loader2 size={14} className="animate-spin" />
                                Saving...
                            </>
                        ) : (
                            <>
                                <Save size={14} />
                                Save
                            </>
                        )}
                    </button>
                </>,
                footerNode
            )}
        </>
    );
};
