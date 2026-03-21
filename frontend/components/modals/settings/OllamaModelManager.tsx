/**
 * Ollama 模型管理组件
 * 
 * 提供模型列表展示、下载、删除、详情查看功能
 */
import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
    Download,
    Trash2,
    RefreshCw,
    HardDrive,
    Info,
    X,
    AlertCircle,
    Loader2,
    ChevronDown,
    ChevronUp
} from 'lucide-react';
import type { OllamaModel, OllamaModelInfo, PullProgress } from '../../../types/ollama';
import { ConfirmDialog } from '../../common/ConfirmDialog';
import {
    getModels,
    getModelInfo,
    deleteModel,
    pullModel,
    formatSize,
    formatDateTime
} from '../../../services/providers/ollama/ollamaApi';

interface OllamaModelManagerProps {
    baseUrl: string;
    apiKey?: string;
    onModelSelect?: (modelId: string) => void;
    onModelsChanged?: () => void;  // 模型列表变化时的回调（下载/删除后）
}

export const OllamaModelManager: React.FC<OllamaModelManagerProps> = ({
    baseUrl,
    apiKey,
    onModelSelect,
    onModelsChanged
}) => {
    // 状态
    const [models, setModels] = useState<OllamaModel[]>([]);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    
    // 下载状态
    const [pullModelName, setPullModelName] = useState('');
    const [isPulling, setIsPulling] = useState(false);
    const [pullProgress, setPullProgress] = useState<PullProgress | null>(null);
    const abortControllerRef = useRef<AbortController | null>(null);
    
    // 详情状态
    const [selectedModel, setSelectedModel] = useState<OllamaModel | null>(null);
    const [modelInfo, setModelInfo] = useState<OllamaModelInfo | null>(null);
    const [isLoadingInfo, setIsLoadingInfo] = useState(false);
    
    // 删除确认
    const [deleteTargetModel, setDeleteTargetModel] = useState<string | null>(null);
    
    // 展开/折叠
    const [isExpanded, setIsExpanded] = useState(true);

    // 加载模型列表
    const loadModels = useCallback(async () => {
        setIsLoading(true);
        setError(null);
        
        try {
            const modelList = await getModels(baseUrl, apiKey);
            setModels(modelList);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to load models');
        } finally {
            setIsLoading(false);
        }
    }, [baseUrl, apiKey]);

    // 初始加载
    useEffect(() => {
        loadModels();
    }, [loadModels]);

    // 查看模型详情
    const handleViewDetails = async (model: OllamaModel) => {
        if (selectedModel?.name === model.name) {
            setSelectedModel(null);
            setModelInfo(null);
            return;
        }
        
        setSelectedModel(model);
        setIsLoadingInfo(true);
        setModelInfo(null);
        
        try {
            const info = await getModelInfo(model.name, baseUrl, apiKey);
            setModelInfo(info);
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to load model info');
        } finally {
            setIsLoadingInfo(false);
        }
    };

    // 删除模型
    const handleDelete = async (modelName: string) => {
        try {
            await deleteModel(modelName, baseUrl, apiKey);
            setModels(prev => prev.filter(m => m.name !== modelName));
            setDeleteTargetModel(null);
            if (selectedModel?.name === modelName) {
                setSelectedModel(null);
                setModelInfo(null);
            }
            // 通知父组件模型列表已变化
            onModelsChanged?.();
        } catch (e) {
            setError(e instanceof Error ? e.message : 'Failed to delete model');
        }
    };

    // 下载模型
    const handlePull = async () => {
        if (!pullModelName.trim() || isPulling) return;
        
        setIsPulling(true);
        setPullProgress({ status: 'Starting download...' });
        setError(null);
        
        abortControllerRef.current = new AbortController();
        
        try {
            await pullModel(
                pullModelName.trim(),
                baseUrl,
                apiKey,
                (progress) => setPullProgress(progress),
                abortControllerRef.current.signal
            );
            
            // 下载成功，刷新列表
            setPullModelName('');
            setPullProgress(null);
            await loadModels();
            // 通知父组件模型列表已变化
            onModelsChanged?.();
        } catch (e) {
            if (e instanceof Error && e.name === 'AbortError') {
                setPullProgress({ status: 'Download cancelled' });
            } else {
                setError(e instanceof Error ? e.message : 'Download failed');
                setPullProgress(null);
            }
        } finally {
            setIsPulling(false);
            abortControllerRef.current = null;
        }
    };

    // 取消下载
    const handleCancelPull = () => {
        abortControllerRef.current?.abort();
    };

    // 计算下载进度百分比
    const progressPercent = pullProgress?.total && pullProgress?.completed
        ? Math.round((pullProgress.completed / pullProgress.total) * 100)
        : null;

    return (
        <>
        <div className="bg-slate-900/30 rounded-xl border border-slate-800/50 overflow-hidden">
            {/* 标题栏 */}
            <button
                onClick={() => setIsExpanded(!isExpanded)}
                className="w-full p-3 flex items-center justify-between hover:bg-slate-800/30 transition-colors"
            >
                <div className="flex items-center gap-2">
                    <HardDrive size={14} className="text-indigo-400" />
                    <span className="text-xs font-bold uppercase tracking-wider text-slate-400">
                        Model Management
                    </span>
                    <span className="text-xs text-slate-600">
                        ({models.length} models)
                    </span>
                </div>
                {isExpanded ? <ChevronUp size={14} className="text-slate-500" /> : <ChevronDown size={14} className="text-slate-500" />}
            </button>

            {isExpanded && (
                <div className="border-t border-slate-800/50">
                    {/* 下载表单 */}
                    <div className="p-3 border-b border-slate-800/50 bg-slate-900/20">
                        <div className="flex gap-2">
                            <input
                                type="text"
                                value={pullModelName}
                                onChange={(e) => setPullModelName(e.target.value)}
                                placeholder="Enter model name (e.g. llama3:latest)"
                                disabled={isPulling}
                                className="flex-1 bg-slate-950 border border-slate-700 rounded-lg px-3 py-2 text-xs focus:border-indigo-500 outline-none text-slate-200 font-mono disabled:opacity-50"
                                onKeyDown={(e) => e.key === 'Enter' && handlePull()}
                            />
                            {isPulling ? (
                                <button
                                    onClick={handleCancelPull}
                                    className="px-3 py-2 bg-red-600/20 hover:bg-red-600/30 text-red-400 rounded-lg text-xs font-medium transition-colors border border-red-600/30 flex items-center gap-1"
                                >
                                    <X size={12} /> Cancel
                                </button>
                            ) : (
                                <button
                                    onClick={handlePull}
                                    disabled={!pullModelName.trim()}
                                    className="px-3 py-2 bg-indigo-600/20 hover:bg-indigo-600/30 text-indigo-400 rounded-lg text-xs font-medium transition-colors border border-indigo-600/30 flex items-center gap-1 disabled:opacity-50 disabled:cursor-not-allowed"
                                >
                                    <Download size={12} /> Pull
                                </button>
                            )}
                        </div>
                        
                        {/* 下载进度 */}
                        {pullProgress && (
                            <div className="mt-2 space-y-1">
                                <div className="flex justify-between text-xs">
                                    <span className="text-slate-400">{pullProgress.status}</span>
                                    {progressPercent !== null && (
                                        <span className="text-indigo-400">{progressPercent}%</span>
                                    )}
                                </div>
                                {progressPercent !== null && (
                                    <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden">
                                        <div
                                            className="h-full bg-indigo-500 transition-all duration-300"
                                            style={{ width: `${progressPercent}%` }}
                                        />
                                    </div>
                                )}
                                {pullProgress.total && pullProgress.completed && (
                                    <div className="text-xs text-slate-500">
                                        {formatSize(pullProgress.completed)} / {formatSize(pullProgress.total)}
                                    </div>
                                )}
                            </div>
                        )}
                    </div>

                    {/* 错误提示 */}
                    {error && (
                        <div className="p-3 bg-red-900/20 border-b border-red-900/30 flex items-start gap-2">
                            <AlertCircle size={14} className="text-red-400 shrink-0 mt-0.5" />
                            <div className="flex-1">
                                <span className="text-xs text-red-300">{error}</span>
                            </div>
                            <button onClick={() => setError(null)} className="text-red-400 hover:text-red-300">
                                <X size={12} />
                            </button>
                        </div>
                    )}

                    {/* 模型列表 */}
                    <div className="p-3">
                        <div className="flex justify-between items-center mb-2">
                            <span className="text-xs text-slate-500">Local Models</span>
                            <button
                                onClick={loadModels}
                                disabled={isLoading}
                                className="text-xs text-slate-400 hover:text-slate-300 flex items-center gap-1"
                            >
                                <RefreshCw size={10} className={isLoading ? 'animate-spin' : ''} />
                                Refresh
                            </button>
                        </div>

                        {isLoading && models.length === 0 ? (
                            <div className="flex items-center justify-center py-8 text-slate-500">
                                <Loader2 size={16} className="animate-spin mr-2" />
                                <span className="text-xs">Loading models...</span>
                            </div>
                        ) : models.length === 0 ? (
                            <div className="text-center py-8 text-slate-500">
                                <HardDrive size={24} className="mx-auto mb-2 opacity-50" />
                                <p className="text-xs">No models installed</p>
                                <p className="text-xs opacity-70 mt-1">Pull a model to get started</p>
                            </div>
                        ) : (
                            <div className="space-y-2">
                                {models.map((model) => (
                                    <div key={model.name} className="bg-slate-900/50 rounded-lg border border-slate-800/50">
                                        <div className="p-2 flex items-center justify-between">
                                            <div
                                                className="flex-1 min-w-0 cursor-pointer"
                                                onClick={() => onModelSelect?.(model.name)}
                                            >
                                                <div className="text-xs font-medium text-slate-200 truncate">
                                                    {model.name}
                                                </div>
                                                <div className="flex items-center gap-2 text-[10px] text-slate-500">
                                                    <span>{formatSize(model.size)}</span>
                                                    <span>•</span>
                                                    <span>{model.details?.family || 'unknown'}</span>
                                                    {model.details?.parameterSize && (
                                                        <>
                                                            <span>•</span>
                                                            <span>{model.details.parameterSize}</span>
                                                        </>
                                                    )}
                                                </div>
                                            </div>
                                            <div className="flex items-center gap-1 ml-2">
                                                <button
                                                    onClick={() => handleViewDetails(model)}
                                                    className={`p-1.5 rounded transition-colors ${
                                                        selectedModel?.name === model.name
                                                            ? 'bg-indigo-600/20 text-indigo-400'
                                                            : 'hover:bg-slate-800 text-slate-400'
                                                    }`}
                                                    title="View details"
                                                >
                                                    <Info size={12} />
                                                </button>
                                                <button
                                                    onClick={() => setDeleteTargetModel(model.name)}
                                                    className="p-1.5 rounded hover:bg-red-600/20 text-slate-400 hover:text-red-400 transition-colors"
                                                    title="Delete model"
                                                >
                                                    <Trash2 size={12} />
                                                </button>
                                            </div>
                                        </div>
                                        
                                        {/* 模型详情面板 */}
                                        {selectedModel?.name === model.name && (
                                            <div className="border-t border-slate-800/50 p-2 bg-slate-950/30">
                                                {isLoadingInfo ? (
                                                    <div className="flex items-center justify-center py-4 text-slate-500">
                                                        <Loader2 size={14} className="animate-spin mr-2" />
                                                        <span className="text-xs">Loading details...</span>
                                                    </div>
                                                ) : modelInfo ? (
                                                    <div className="space-y-2">
                                                        <div className="grid grid-cols-2 gap-2 text-xs">
                                                            <div>
                                                                <span className="text-slate-500">Family:</span>
                                                                <span className="ml-1 text-slate-300">{modelInfo.details?.family || 'N/A'}</span>
                                                            </div>
                                                            <div>
                                                                <span className="text-slate-500">Parameters:</span>
                                                                <span className="ml-1 text-slate-300">{modelInfo.details?.parameterSize || 'N/A'}</span>
                                                            </div>
                                                            <div>
                                                                <span className="text-slate-500">Format:</span>
                                                                <span className="ml-1 text-slate-300">{modelInfo.details?.format || 'N/A'}</span>
                                                            </div>
                                                            <div>
                                                                <span className="text-slate-500">Quantization:</span>
                                                                <span className="ml-1 text-slate-300">{modelInfo.details?.quantizationLevel || 'N/A'}</span>
                                                            </div>
                                                        </div>
                                                        <div>
                                                            <span className="text-xs text-slate-500">Capabilities:</span>
                                                            <div className="flex flex-wrap gap-1 mt-1">
                                                                {modelInfo.capabilities?.map((cap) => (
                                                                    <span
                                                                        key={cap}
                                                                        className="px-1.5 py-0.5 bg-indigo-600/20 text-indigo-300 rounded text-[10px] font-medium"
                                                                    >
                                                                        {cap}
                                                                    </span>
                                                                ))}
                                                            </div>
                                                        </div>
                                                        <div className="text-[10px] text-slate-600">
                                                            Modified: {formatDateTime(model.modifiedAt)}
                                                        </div>
                                                    </div>
                                                ) : null}
                                            </div>
                                        )}
                                    </div>
                                ))}
                            </div>
                        )}
                    </div>
                </div>
            )}
        </div>
      <ConfirmDialog
          isOpen={!!deleteTargetModel}
          title="Delete Model"
          message={`Are you sure you want to delete model "${deleteTargetModel}"?`}
          confirmLabel="Delete"
          cancelLabel="Cancel"
          onConfirm={() => {
              if (deleteTargetModel) {
                  handleDelete(deleteTargetModel);
              }
          }}
          onCancel={() => setDeleteTargetModel(null)}
      />
        </>
    );
};

export default OllamaModelManager;
