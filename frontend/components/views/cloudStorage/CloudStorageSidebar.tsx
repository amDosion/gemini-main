import React from 'react';
import { Folder } from 'lucide-react';
import type { StorageBrowseItem, StorageConfig } from '../../../types/storage';
import { providerLabel } from './filePresentation';

interface CloudStorageSidebarProps {
  storageName: string;
  selectedStorageName?: string;
  provider: string;
  selectedProvider?: string;
  orderedStorageConfigs: StorageConfig[];
  selectedStorageId: string | null;
  activeStorageId: string | null;
  currentPath: string;
  directories: StorageBrowseItem[];
  onSelectStorage: (storageId: string) => void;
  onClickRoot: () => void;
  onOpenDirectory: (path: string) => void;
}

export const CloudStorageSidebar: React.FC<CloudStorageSidebarProps> = ({
  storageName,
  selectedStorageName,
  provider,
  selectedProvider,
  orderedStorageConfigs,
  selectedStorageId,
  activeStorageId,
  currentPath,
  directories,
  onSelectStorage,
  onClickRoot,
  onOpenDirectory
}) => {
  const sectionClass = 'border-b border-slate-800/70';
  const sectionTitleClass = 'flex h-9 items-center px-3 text-[11px] font-bold uppercase tracking-wider text-slate-500';
  const activeProviderLabel = providerLabel(provider || selectedProvider || '-');
  const currentStorageLabel = storageName || selectedStorageName || 'None';

  return (
    <div className="min-h-full">
      <section className={sectionClass}>
        <div className="px-3 py-2.5">
          <div className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Current Storage</div>
          <div className="mt-1 truncate text-xs text-slate-100">{currentStorageLabel}</div>
          <div className="mt-1 text-[11px] text-slate-500">{activeProviderLabel}</div>
        </div>
      </section>

      <section className={sectionClass}>
        <div className={sectionTitleClass}>Configured Storages</div>
        {orderedStorageConfigs.length === 0 ? (
          <p className="px-3 py-3 text-xs text-slate-500">No storage config</p>
        ) : (
          orderedStorageConfigs.map((config) => {
            const isSelected = config.id === selectedStorageId;
            const isActive = config.id === activeStorageId;
            return (
              <button
                key={config.id}
                type="button"
                disabled={!config.enabled}
                onClick={() => onSelectStorage(config.id)}
                className={`flex w-full items-start gap-2.5 border-t border-slate-800/60 px-3 py-2.5 text-left transition-colors first:border-t-0 ${
                  isSelected
                    ? 'bg-indigo-500/10 text-indigo-100'
                    : 'text-slate-200 hover:bg-slate-900/60'
                } ${!config.enabled ? 'cursor-not-allowed opacity-50' : ''}`}
              >
                <div className={`mt-0.5 inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md ${
                  isSelected ? 'bg-indigo-600 text-white' : 'bg-slate-800/80 text-slate-400'
                }`}>
                  <Folder size={15} />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-xs font-semibold">{config.name}</span>
                    {isActive && (
                      <span className="inline-flex h-5 shrink-0 items-center rounded border border-indigo-500/30 px-1.5 text-[10px] text-indigo-300">
                        Active
                      </span>
                    )}
                  </div>
                  <div className="mt-0.5 flex items-center justify-between gap-2">
                    <span className="truncate text-[11px] text-slate-500">{providerLabel(config.provider)}</span>
                    {!config.enabled && (
                      <span className="text-[10px] text-slate-500">Disabled</span>
                    )}
                  </div>
                </div>
              </button>
            );
          })
        )}
      </section>

      <section className={sectionClass}>
        <div className={sectionTitleClass}>Folders</div>
        <button
          type="button"
          onClick={onClickRoot}
          className={`flex w-full items-center gap-2.5 px-3 py-2.5 text-left text-xs transition-colors ${
            currentPath
              ? 'text-slate-300 hover:bg-slate-900/60'
              : 'bg-indigo-500/10 text-indigo-100'
          }`}
        >
          <div className={`inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md ${
            currentPath ? 'bg-slate-800/80 text-slate-400' : 'bg-indigo-600 text-white'
          }`}>
            <Folder size={15} />
          </div>
          <span className="truncate font-semibold">Root</span>
        </button>
        {directories.length === 0 ? (
          <p className="border-t border-slate-800/60 px-3 py-3 text-xs text-slate-500">No folders</p>
        ) : (
          directories.map((dir) => (
            <button
              key={dir.path}
              type="button"
              onClick={() => onOpenDirectory(dir.path)}
              className="flex w-full items-center gap-2.5 border-t border-slate-800/60 px-3 py-2.5 text-left text-xs text-slate-300 transition-colors hover:bg-slate-900/60"
            >
              <div className="inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-slate-800/80 text-slate-400">
                <Folder size={15} />
              </div>
              <span className="truncate font-semibold">{dir.name}</span>
            </button>
          ))
        )}
      </section>
    </div>
  );
};
