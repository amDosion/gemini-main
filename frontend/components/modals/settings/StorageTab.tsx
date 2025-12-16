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
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <Cloud className="text-indigo-400" size={28} />
          <h2 className="text-2xl font-bold text-white">Cloud Storage Configuration</h2>
        </div>
        <p className="text-slate-400 text-sm">
          Configure image storage services, supports Lsky Pro and Aliyun OSS
        </p>
      </div>

      {/* Create New Button */}
      <button
        onClick={onCreateNew}
        className="w-full mb-6 px-6 py-4 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl font-medium transition-colors flex items-center justify-center gap-2 shadow-lg shadow-indigo-900/20"
      >
        <Plus size={20} />
        Add New Storage Configuration
      </button>

      {/* Storage List */}
      {storageConfigs.length === 0 ? (
        <div className="text-center py-16 bg-slate-900/30 rounded-xl border border-slate-800">
          <Cloud className="mx-auto mb-4 text-slate-600" size={48} />
          <p className="text-slate-400 mb-2">No storage configuration</p>
          <p className="text-slate-500 text-sm">Click the button above to add the first configuration</p>
        </div>
      ) : (
        <div className="space-y-3">
          {storageConfigs.map((config) => {
            const isActive = config.id === activeStorageId;
            const isDeleting = deletingId === config.id;

            return (
              <div
                key={config.id}
                className={`p-5 rounded-xl border transition-all ${isActive
                    ? 'bg-indigo-900/20 border-indigo-500/50 shadow-lg shadow-indigo-900/10'
                    : 'bg-slate-900/50 border-slate-800 hover:border-slate-700'
                  }`}
              >
                <div className="flex items-start justify-between">
                  {/* Left: Info */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="text-lg font-semibold text-white truncate">
                        {config.name}
                      </h3>
                      {isActive && (
                        <span className="flex items-center gap-1 px-2 py-1 bg-green-500/10 text-green-400 text-xs font-medium rounded-lg border border-green-500/20">
                          <Check size={12} />
                          Active
                        </span>
                      )}
                      {!config.enabled && (
                        <span className="px-2 py-1 bg-slate-500/10 text-slate-400 text-xs font-medium rounded-lg border border-slate-500/20">
                          Disabled
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-2 mb-3">
                      <span
                        className={`px-2 py-1 text-xs font-medium rounded-lg border ${getProviderColor(
                          config.provider
                        )}`}
                      >
                        {getProviderLabel(config.provider)}
                      </span>
                    </div>

                    {/* Config Details */}
                    <div className="text-sm text-slate-400 space-y-1">
                      {config.provider === 'lsky' && 'domain' in config.config && (
                        <div>Domain: {config.config.domain}</div>
                      )}
                      {config.provider === 'aliyun-oss' && 'bucket' in config.config && (
                        <div>
                          Bucket: {config.config.bucket} ({config.config.region})
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Right: Actions */}
                  <div className="flex items-center gap-2 ml-4">
                    {!isActive && config.enabled && (
                      <button
                        onClick={() => onActivateStorage(config.id)}
                        className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium rounded-lg transition-colors"
                      >
                        Set as Active
                      </button>
                    )}

                    <button
                      onClick={() => onEditStorage(config)}
                      className="p-2 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors"
                      title="Edit"
                    >
                      <Edit2 size={18} />
                    </button>

                    <button
                      onClick={() => handleDelete(config.id)}
                      className={`p-2 rounded-lg transition-colors ${isDeleting
                          ? 'bg-red-600 text-white'
                          : 'text-slate-400 hover:text-red-400 hover:bg-slate-800'
                        }`}
                      title={isDeleting ? 'Click again to confirm delete' : 'Delete'}
                    >
                      <Trash2 size={18} />
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Info Box */}
      <div className="mt-8 p-4 bg-blue-500/5 border border-blue-500/20 rounded-xl">
        <h4 className="text-sm font-semibold text-blue-400 mb-2">💡 Instructions</h4>
        <ul className="text-sm text-slate-400 space-y-1">
          <li>• Lsky Pro: Requires Domain and API Token</li>
          <li>• Aliyun OSS: Requires AccessKey, Bucket, and Region</li>
          <li>• Only one storage configuration can be active at a time</li>
          <li>• Image extensions will use the currently active storage service</li>
        </ul>
      </div>
    </div>
  );
};
