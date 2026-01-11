
/**
 * Cloud Storage Configuration Tab
 */

import React, { useState } from 'react';
import { Cloud, Plus, Trash2, Check, Edit2 } from 'lucide-react';
import { StorageConfig, StorageProvider } from '../../../types/storage';

interface StorageTabProps {
  storageConfigs: StorageConfig[];
  activeStorageId: string | null;
  onSaveStorage: (config: StorageConfig) => Promise<void>;
  onDeleteStorage: (id: string) => Promise<void>;
  onActivateStorage: (id: string) => Promise<void>;
  onCreateNew: () => void;
  onEditStorage: (config: StorageConfig) => void;
}

export const StorageTab: React.FC<StorageTabProps> = ({
  storageConfigs,
  activeStorageId,
  onSaveStorage,
  onDeleteStorage,
  onActivateStorage,
  onCreateNew,
  onEditStorage
}) => {
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const handleDelete = async (id: string) => {
    if (deletingId === id) {
      await onDeleteStorage(id);
      setDeletingId(null);
    } else {
      setDeletingId(id);
      setTimeout(() => setDeletingId(null), 3000);
    }
  };

  const getProviderLabel = (provider: StorageProvider): string => {
    switch (provider) {
      case 'lsky':
        return 'Lsky Pro';
      case 'aliyun-oss':
        return 'Aliyun OSS';
      case 'local':
        return 'Local Storage';
      default:
        return provider;
    }
  };

  const getProviderColor = (provider: StorageProvider): string => {
    switch (provider) {
      case 'lsky':
        return 'bg-blue-500/10 text-blue-400 border-blue-500/20';
      case 'aliyun-oss':
        return 'bg-orange-500/10 text-orange-400 border-orange-500/20';
      case 'local':
        return 'bg-gray-500/10 text-gray-400 border-gray-500/20';
      default:
        return 'bg-slate-500/10 text-slate-400 border-slate-500/20';
    }
  };

  return (
    <div className="absolute inset-0 flex flex-col p-3 md:p-6 space-y-4 md:space-y-6">
      {/* Header */}
      <div className="shrink-0 flex items-center justify-between pb-3 md:pb-4 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h2 className="text-base md:text-lg font-medium text-white">Cloud Storage</h2>
          </div>
          <p className="text-xs text-slate-500">
            Configure image storage services.
          </p>
        </div>
        <button
          onClick={onCreateNew}
          className="flex items-center gap-2 px-3 py-1.5 md:px-4 md:py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs md:text-sm font-medium transition-colors shadow-lg shadow-indigo-500/20"
        >
          <Plus size={14} className="md:w-4 md:h-4" /> <span className="hidden md:inline">New Sorage</span><span className="md:hidden">New</span>
        </button>
      </div>

      <div className="flex-1 flex flex-col min-h-0 overflow-hidden">

        {/* Storage List */}
        <div className="flex-1 overflow-y-auto min-h-0 custom-scrollbar pr-1 pb-4 md:pb-4">
          {storageConfigs.length === 0 ? (
            <div className="text-center py-12 md:py-16 bg-slate-900/30 rounded-xl border border-slate-800 h-full flex flex-col items-center justify-center">
              <Cloud className="mx-auto mb-4 text-slate-600" size={40} />
              <p className="text-slate-400 mb-2 text-sm">No storage configuration</p>
              <p className="text-slate-500 text-xs">Click the button above to add one.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {storageConfigs.map((config) => {
                const isActive = config.id === activeStorageId;
                const isDeleting = deletingId === config.id;

                return (
                  <div
                    key={config.id}
                    className={`p-4 md:p-5 rounded-xl border transition-all ${isActive
                      ? 'bg-indigo-900/20 border-indigo-500/50 shadow-lg shadow-indigo-900/10'
                      : 'bg-slate-900/50 border-slate-800 hover:border-slate-700'
                      }`}
                  >
                    <div className="flex items-center justify-between gap-3">
                      {/* Left: Info */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <h3 className="text-sm md:text-base font-medium text-slate-200 truncate">
                            {config.name}
                          </h3>
                          {isActive && (
                            <span className="flex items-center gap-1 px-1.5 py-0.5 bg-indigo-500/10 text-indigo-400 text-[10px] font-bold rounded border border-indigo-500/20 shrink-0">
                              Active
                            </span>
                          )}
                          {!config.enabled && (
                            <span className="px-1.5 py-0.5 bg-slate-500/10 text-slate-500 text-[10px] font-medium rounded border border-slate-500/20 shrink-0">
                              Disabled
                            </span>
                          )}
                        </div>

                        <div className="flex items-center gap-2 text-xs text-slate-500">
                          <span
                            className={`px-1.5 py-0 rounded text-[10px] font-mono border ${getProviderColor(
                              config.provider
                            )}`}
                          >
                            {getProviderLabel(config.provider)}
                          </span>
                          <span className="truncate opacity-70 font-mono">
                            {config.provider === 'lsky' && 'domain' in config.config && config.config.domain}
                            {config.provider === 'aliyun-oss' && 'bucket' in config.config && config.config.bucket}
                          </span>
                        </div>
                      </div>

                      {/* Right: Actions */}
                      <div className="flex items-center gap-1 shrink-0 ml-2">
                        {!isActive && config.enabled && (
                          <button
                            onClick={() => onActivateStorage(config.id)}
                            className="p-1.5 bg-slate-800 hover:bg-indigo-600 hover:text-white text-slate-400 rounded-lg transition-colors border border-slate-700"
                            title="Activate"
                          >
                            <Check size={16} className="md:w-[14px] md:h-[14px]" />
                          </button>
                        )}

                        <button
                          onClick={() => onEditStorage(config)}
                          className="p-1.5 bg-slate-800 hover:bg-slate-700 hover:text-white text-slate-400 rounded-lg transition-colors border border-slate-700"
                          title="Edit"
                        >
                          <Edit2 size={16} className="md:w-[14px] md:h-[14px]" />
                        </button>

                        <button
                          onClick={() => handleDelete(config.id)}
                          className={`p-1.5 rounded-lg transition-colors border ${isDeleting
                            ? 'bg-red-900/50 text-red-200 border-red-500'
                            : 'bg-slate-800 text-slate-400 hover:text-white hover:bg-red-600 border-slate-700'
                            }`}
                          title={isDeleting ? 'Click again to confirm delete' : 'Delete'}
                        >
                          <Trash2 size={16} className="md:w-[14px] md:h-[14px]" />
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
