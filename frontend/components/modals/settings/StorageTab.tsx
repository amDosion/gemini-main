
/**
 * Cloud Storage Configuration Tab
 */

import React, { useEffect, useState } from 'react';
import { Cloud, Plus, Trash2, Check, Edit2, MoreHorizontal } from 'lucide-react';
import { StorageConfig, StorageProvider } from '../../../types/storage';
import { ConfirmDialog } from '../../common/ConfirmDialog';

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
  const [deleteTargetId, setDeleteTargetId] = useState<string | null>(null);
  const [openMenuId, setOpenMenuId] = useState<string | null>(null);

  const handleDeleteClick = (id: string) => {
    setDeleteTargetId(id);
    setOpenMenuId(null);
  };

  const handleDeleteConfirm = async () => {
    if (deleteTargetId) {
      await onDeleteStorage(deleteTargetId);
    }
    setDeleteTargetId(null);
  };

  const handleDeleteCancel = () => {
    setDeleteTargetId(null);
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

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as HTMLElement | null;
      if (target?.closest('[data-storage-card-actions]')) {
        return;
      }
      setOpenMenuId(null);
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

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
          <Plus size={14} className="md:w-4 md:h-4" /> <span className="hidden md:inline">New Storage</span><span className="md:hidden">New</span>
        </button>
      </div>

      <div className="flex-1 overflow-y-auto min-h-0 custom-scrollbar pr-1 pb-4 md:pb-4">
        {storageConfigs.length === 0 ? (
          <div className="text-center py-16 bg-slate-900/30 rounded-xl border border-slate-800 h-full flex flex-col items-center justify-center">
            <Cloud className="mx-auto mb-4 text-slate-600" size={40} />
            <p className="text-slate-400 mb-2 text-sm">No storage configuration</p>
            <p className="text-slate-500 text-xs">Click the button above to add one.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
            {storageConfigs.map((config) => {
              const isActive = config.id === activeStorageId;
              const isMenuOpen = openMenuId === config.id;

              const endpointSummary =
                (config.provider === 'lsky' && 'domain' in config.config && config.config.domain) ||
                (config.provider === 'aliyun-oss' && 'bucket' in config.config && config.config.bucket) ||
                'No endpoint summary';

              return (
                <div
                  key={config.id}
                  className={`group rounded-xl border bg-slate-900/50 border-slate-800 hover:border-slate-700 transition-all p-4 md:p-5 h-full flex flex-col ${isActive ? 'border-indigo-500/50 shadow-lg shadow-indigo-900/10' : ''
                    }`}
                >
                  <div className="flex items-start justify-between gap-2 mb-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <h3 className="text-sm md:text-base font-medium text-slate-200 truncate">
                        {config.name}
                      </h3>
                      <div className="relative shrink-0" data-storage-card-actions>
                        <button
                          type="button"
                          onClick={() => setOpenMenuId((prev) => (prev === config.id ? null : config.id))}
                          className={`p-1.5 rounded-lg border border-slate-700 bg-slate-800 text-slate-400 hover:text-white hover:bg-slate-700 transition-all ${isMenuOpen ? 'opacity-100' : 'opacity-0 group-hover:opacity-100 group-focus-within:opacity-100'
                            }`}
                          title="Actions"
                        >
                          <MoreHorizontal size={14} />
                        </button>

                        {isMenuOpen && (
                          <div className="absolute left-0 top-9 z-20 w-40 rounded-lg border border-slate-700 bg-slate-900 shadow-xl p-1">
                            {!isActive && config.enabled && (
                              <button
                                type="button"
                                onClick={() => {
                                  void onActivateStorage(config.id);
                                  setOpenMenuId(null);
                                }}
                                className="w-full flex items-center gap-2 px-2 py-1.5 text-xs text-slate-300 hover:bg-slate-800 rounded"
                              >
                                <Check size={13} />
                                <span>Activate</span>
                              </button>
                            )}

                            <button
                              type="button"
                              onClick={() => {
                                onEditStorage(config);
                                setOpenMenuId(null);
                              }}
                              className="w-full flex items-center gap-2 px-2 py-1.5 text-xs text-slate-300 hover:bg-slate-800 rounded"
                            >
                              <Edit2 size={13} />
                              <span>Edit</span>
                            </button>

                            <button
                              type="button"
                              onClick={() => handleDeleteClick(config.id)}
                              className="w-full flex items-center gap-2 px-2 py-1.5 text-xs text-red-300 hover:bg-red-900/30 rounded"
                            >
                              <Trash2 size={13} />
                              <span>Delete</span>
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      <span
                        className={`px-1.5 py-0.5 text-[10px] font-mono rounded border ${getProviderColor(
                          config.provider
                        )}`}
                      >
                        {getProviderLabel(config.provider)}
                      </span>
                      {isActive && (
                        <span className="px-1.5 py-0.5 bg-indigo-500/10 text-indigo-400 text-[10px] font-medium rounded border border-indigo-500/20">
                          Active
                        </span>
                      )}
                      {!config.enabled && (
                        <span className="px-1.5 py-0.5 bg-slate-500/10 text-slate-400 text-[10px] font-medium rounded border border-slate-500/20">
                          Disabled
                        </span>
                      )}
                    </div>
                  </div>

                  <div className="text-xs text-slate-500 font-mono break-all">
                    {endpointSummary}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
      <ConfirmDialog
        isOpen={!!deleteTargetId}
        title="Delete Storage"
        message="Are you sure you want to delete this storage configuration?"
        confirmLabel="Delete"
        cancelLabel="Cancel"
        onConfirm={handleDeleteConfirm}
        onCancel={handleDeleteCancel}
      />
    </div>
  );
};
