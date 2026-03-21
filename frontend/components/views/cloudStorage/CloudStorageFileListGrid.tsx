import React, { useEffect, useState } from 'react';
import type { MutableRefObject } from 'react';
import { CheckSquare, Copy, Download, Eye, MoreHorizontal, Pencil, Square, Trash2 } from 'lucide-react';
import type { StorageBrowseItem, StorageFileMetadataItem } from '../../../types/storage';
import {
  formatBytes,
  formatDate,
  getFileExtension
} from './filePresentation';
import { CloudStorageThumbnailCell } from './CloudStorageThumbnailCell';

type ActionMenuDirection = 'down' | 'up';
const GRID_CARD_WIDTH = 160;

interface CloudStorageFileListGridProps {
  viewMode: 'list' | 'grid';
  pagedItems: StorageBrowseItem[];
  selectedPaths: Set<string>;
  onToggleSelectItem: (path: string) => void;
  onViewItem: (item: StorageBrowseItem) => void;
  onDownloadItem: (item: StorageBrowseItem) => Promise<void>;
  onCopyUrl: (item: StorageBrowseItem) => Promise<void>;
  onRenameItem: (item: StorageBrowseItem) => Promise<void>;
  onDeleteItem: (item: StorageBrowseItem) => Promise<void>;
  fileMetadataByUrl: Record<string, StorageFileMetadataItem>;
  failedPreviewUrlsRef: MutableRefObject<Set<string>>;
  storageRevision: number | null;
  suspendPreviewLoading?: boolean;
}

export const CloudStorageFileListGrid: React.FC<CloudStorageFileListGridProps> = ({
  viewMode,
  pagedItems,
  selectedPaths,
  onToggleSelectItem,
  onViewItem,
  onDownloadItem,
  onCopyUrl,
  onRenameItem,
  onDeleteItem,
  fileMetadataByUrl,
  failedPreviewUrlsRef,
  storageRevision,
  suspendPreviewLoading = false
}) => {
  const [openActionMenuPath, setOpenActionMenuPath] = useState<string | null>(null);

  useEffect(() => {
    const handleOutsideClick = (event: MouseEvent) => {
      const target = event.target as HTMLElement | null;
      if (target?.closest('[data-cloud-item-actions]')) {
        return;
      }
      setOpenActionMenuPath(null);
    };

    document.addEventListener('mousedown', handleOutsideClick);
    return () => {
      document.removeEventListener('mousedown', handleOutsideClick);
    };
  }, []);

  useEffect(() => {
    setOpenActionMenuPath(null);
  }, [viewMode, pagedItems]);

  const renderItemActions = (
    item: StorageBrowseItem,
    options: { compact?: boolean; menuDirection?: ActionMenuDirection } = {}
  ) => {
    const compact = options.compact ?? false;
    const menuDirection = options.menuDirection ?? 'down';
    const isDirectory = item.entryType === 'directory';
    const isOpen = openActionMenuPath === item.path;
    const iconSize = compact ? 13 : 14;
    const actionButtonClass = 'p-1.5 rounded-md text-slate-400 hover:text-white hover:bg-slate-800';

    return (
      <div
        data-cloud-item-actions
        className={`relative ${compact ? '' : 'shrink-0'} ${
          isOpen ? 'opacity-100' : 'md:opacity-0 md:group-hover:opacity-100 md:group-focus-within:opacity-100'
        } transition-opacity`}
      >
        <button
          type="button"
          onClick={() => setOpenActionMenuPath((prev) => (prev === item.path ? null : item.path))}
          className={actionButtonClass}
          title="Actions"
        >
          <MoreHorizontal size={iconSize} />
        </button>

        {isOpen && (
          <div
            className={`absolute right-0 z-20 min-w-36 rounded-lg border border-slate-700 bg-slate-900 shadow-xl p-1 ${
              menuDirection === 'up' ? 'bottom-8' : 'top-8'
            }`}
          >
            <button
              type="button"
              onClick={() => {
                setOpenActionMenuPath(null);
                onViewItem(item);
              }}
              className="w-full flex items-center gap-2 px-2 py-1.5 text-xs text-slate-300 hover:bg-slate-800 rounded"
            >
              <Eye size={13} />
              <span>{isDirectory ? 'Open Folder' : 'View'}</span>
            </button>

            <button
              type="button"
              onClick={() => {
                setOpenActionMenuPath(null);
                void onDownloadItem(item);
              }}
              className="w-full flex items-center gap-2 px-2 py-1.5 text-xs text-slate-300 hover:bg-slate-800 rounded"
            >
              <Download size={13} />
              <span>{isDirectory ? 'Download Folder' : 'Download'}</span>
            </button>

            {!isDirectory && item.url && (
              <button
                type="button"
                onClick={() => {
                  setOpenActionMenuPath(null);
                  void onCopyUrl(item);
                }}
                className="w-full flex items-center gap-2 px-2 py-1.5 text-xs text-slate-300 hover:bg-slate-800 rounded"
              >
                <Copy size={13} />
                <span>Copy URL</span>
              </button>
            )}

            <button
              type="button"
              onClick={() => {
                setOpenActionMenuPath(null);
                void onRenameItem(item);
              }}
              className="w-full flex items-center gap-2 px-2 py-1.5 text-xs text-slate-300 hover:bg-slate-800 rounded"
            >
              <Pencil size={13} />
              <span>Rename</span>
            </button>

            <button
              type="button"
              onClick={() => {
                setOpenActionMenuPath(null);
                void onDeleteItem(item);
              }}
              className="w-full flex items-center gap-2 px-2 py-1.5 text-xs text-red-300 hover:bg-red-900/30 rounded"
            >
              <Trash2 size={13} />
              <span>Delete</span>
            </button>
          </div>
        )}
      </div>
    );
  };

  if (viewMode === 'list') {
    return (
      <div className="divide-y divide-slate-800/80">
        {pagedItems.map((item) => {
          const isDirectory = item.entryType === 'directory';
          const fileExt = getFileExtension(item.name);
          const isSelected = selectedPaths.has(item.path);
          const metadata = item.metadata || (item.url ? fileMetadataByUrl[item.url] : undefined);
          return (
            <div key={`${item.entryType}:${item.path}`} className="group px-4 md:px-6 py-3 flex items-center gap-3 hover:bg-slate-900/60">
              <button
                type="button"
                onClick={() => onToggleSelectItem(item.path)}
                className="text-slate-400 hover:text-white"
                title={isSelected ? 'Unselect' : 'Select'}
              >
                {isSelected ? <CheckSquare size={15} /> : <Square size={15} />}
              </button>

              <CloudStorageThumbnailCell
                item={item}
                failedPreviewUrlsRef={failedPreviewUrlsRef}
                storageRevision={storageRevision}
                disablePreview={suspendPreviewLoading}
              />

              <button
                type="button"
                onClick={() => onViewItem(item)}
                className={`text-left min-w-0 flex-1 ${isDirectory ? 'text-slate-100 hover:text-indigo-300' : 'text-slate-200'}`}
                title={item.path}
              >
                <div className="truncate text-sm flex items-center gap-2">
                  <span>{item.name}</span>
                  {!isDirectory && fileExt && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded border border-slate-700 text-slate-400 bg-slate-900/80 uppercase">
                      {fileExt}
                    </span>
                  )}
                </div>
              </button>

              <div className="hidden md:block text-xs text-slate-500 w-28 text-right">
                {isDirectory ? '-' : formatBytes(item.size ?? metadata?.contentLength ?? null)}
              </div>

              <div className="hidden md:block text-xs text-slate-500 w-44 text-right">
                {formatDate(item.updatedAt)}
              </div>

              {renderItemActions(item)}
            </div>
          );
        })}
      </div>
    );
  }

  return (
    <div
      className="p-2 grid gap-3 justify-center md:justify-start"
      style={{ gridTemplateColumns: `repeat(auto-fit, minmax(${GRID_CARD_WIDTH}px, ${GRID_CARD_WIDTH}px))` }}
    >
      {pagedItems.map((item) => {
        const isDirectory = item.entryType === 'directory';
        const fileExt = getFileExtension(item.name);
        const isSelected = selectedPaths.has(item.path);
        const metadata = item.metadata || (item.url ? fileMetadataByUrl[item.url] : undefined);
        return (
          <div
            key={`${item.entryType}:${item.path}`}
            className="group rounded-xl border border-slate-800 bg-slate-900/50 hover:border-slate-700 transition-colors p-2.5 flex flex-col gap-2 relative"
          >
            <div className="relative">
              <button
                type="button"
                onClick={() => onViewItem(item)}
                className="w-full"
                title={isDirectory ? 'Open folder' : 'View'}
              >
                <CloudStorageThumbnailCell
                  item={item}
                  failedPreviewUrlsRef={failedPreviewUrlsRef}
                  storageRevision={storageRevision}
                  sizeClassName="h-24 w-full"
                  disablePreview={suspendPreviewLoading}
                />
              </button>

              <button
                type="button"
                onClick={(event) => {
                  event.stopPropagation();
                  onToggleSelectItem(item.path);
                }}
                className={`absolute left-2 top-2 text-slate-300 bg-slate-900/90 rounded-md p-0.5 border border-slate-700 transition-opacity ${
                  isSelected ? 'opacity-100' : 'opacity-0 group-hover:opacity-100 group-focus-within:opacity-100'
                }`}
                title={isSelected ? 'Unselect' : 'Select'}
              >
                {isSelected ? <CheckSquare size={14} /> : <Square size={14} />}
              </button>
            </div>

            <button
              type="button"
              onClick={() => onViewItem(item)}
              className="text-left"
              title={item.path}
            >
              <p className={`text-sm truncate ${isDirectory ? 'text-slate-100 hover:text-indigo-300' : 'text-slate-200'}`}>
                {item.name}
              </p>
            </button>

            <div className="flex items-center justify-between text-[11px] text-slate-500">
              <span className="truncate pr-2">
                {isDirectory
                  ? '-'
                  : `${formatBytes(item.size ?? metadata?.contentLength ?? null)} · ${fileExt ? fileExt.toUpperCase() : 'FILE'}`}
              </span>
              {renderItemActions(item, { compact: true, menuDirection: 'up' })}
            </div>
          </div>
        );
      })}
    </div>
  );
};
