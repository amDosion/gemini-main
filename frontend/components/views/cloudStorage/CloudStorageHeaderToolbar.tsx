import React from 'react';
import {
  ArrowLeft,
  CheckSquare,
  ChevronRight,
  Download,
  Grid3X3,
  List,
  RefreshCw,
  Search,
  Upload
} from 'lucide-react';
import {
  flatToolbarBarClass,
  flatToolbarButtonClass,
  flatToolbarDangerButtonClass,
  flatToolbarLabelClass,
  flatToolbarSearchInputClass,
  flatToolbarSearchWrapClass,
  flatToolbarSectionClass,
  flatToolbarSeparatorClass
} from '../../common/flatToolbarStyles';

type ViewMode = 'list' | 'grid';

interface CloudStorageHeaderToolbarProps {
  currentPath: string;
  pathSegments: string[];
  canBrowse: boolean;
  hasSelectableItems: boolean;
  hasVisibleSelection: boolean;
  selectedCount: number;
  actionDisabled: boolean;
  searchQuery: string;
  viewMode: ViewMode;
  loading: boolean;
  loadingMore: boolean;
  onBreadcrumbClick: (index: number) => void;
  onBulkSelectAction: () => void;
  onBatchDownload: () => Promise<void>;
  onBatchDelete: () => Promise<void>;
  onSearchQueryChange: (query: string) => void;
  onViewModeChange: (mode: ViewMode) => void;
  onOpenUploadPicker: () => void;
  onRefresh: () => void;
  onClose: () => void;
}

export const CloudStorageHeaderToolbar: React.FC<CloudStorageHeaderToolbarProps> = ({
  currentPath,
  pathSegments,
  canBrowse,
  hasSelectableItems,
  hasVisibleSelection,
  selectedCount,
  actionDisabled,
  searchQuery,
  viewMode,
  loading,
  loadingMore,
  onBreadcrumbClick,
  onBulkSelectAction,
  onBatchDownload,
  onBatchDelete,
  onSearchQueryChange,
  onViewModeChange,
  onOpenUploadPicker,
  onRefresh,
  onClose
}) => {
  const bulkSelectLabel = hasVisibleSelection ? 'Invert' : 'Select All';
  const breadcrumbButtonClass =
    'shrink-0 h-full inline-flex items-center px-1.5 text-xs leading-none text-slate-400 hover:text-white transition-colors';

  return (
    <div className={flatToolbarBarClass}>
      <div className="min-w-0 h-full flex items-center gap-0.5 overflow-x-auto custom-scrollbar">
        <button
          type="button"
          onClick={() => onBreadcrumbClick(-1)}
          className={`${breadcrumbButtonClass} ${
            currentPath
              ? ''
              : 'text-indigo-300'
          }`}
        >
          Root
        </button>
        {pathSegments.map((segment, index) => (
          <React.Fragment key={`header-${segment}-${index}`}>
            <ChevronRight size={11} className="text-slate-700 shrink-0" />
            <button
              type="button"
              onClick={() => onBreadcrumbClick(index)}
              className={`${breadcrumbButtonClass} ${
                index === pathSegments.length - 1
                  ? 'text-indigo-300'
                  : ''
              }`}
            >
              {segment}
            </button>
          </React.Fragment>
        ))}
      </div>

      <div className={flatToolbarSectionClass}>
        {canBrowse && (
          <>
            <button
              type="button"
              onClick={onBulkSelectAction}
              disabled={!hasSelectableItems || actionDisabled}
              className={flatToolbarButtonClass}
            >
              <CheckSquare size={13} />
              <span className="hidden md:inline">{bulkSelectLabel}</span>
            </button>
            <span className={flatToolbarLabelClass}>
              {selectedCount} selected
            </span>
            <button
              type="button"
              onClick={() => void onBatchDownload()}
              disabled={selectedCount === 0 || actionDisabled}
              className={flatToolbarButtonClass}
            >
              <Download size={12} />
              Download
            </button>
            <button
              type="button"
              onClick={() => void onBatchDelete()}
              disabled={selectedCount === 0 || actionDisabled}
              className={flatToolbarDangerButtonClass}
            >
              Delete
            </button>
            <span className={flatToolbarSeparatorClass}>｜</span>
          </>
        )}

        <label className={`${flatToolbarSearchWrapClass} w-44 md:w-52`}>
          <Search size={13} className="absolute left-1 top-1/2 -translate-y-1/2 text-slate-600" />
          <input
            type="text"
            value={searchQuery}
            onChange={(event) => onSearchQueryChange(event.target.value)}
            placeholder="Search by name or path"
            className={flatToolbarSearchInputClass}
          />
        </label>
        <span className={flatToolbarSeparatorClass}>｜</span>

        <button
          type="button"
          onClick={() => onViewModeChange('list')}
          className={`${flatToolbarButtonClass} ${viewMode === 'list' ? 'text-white' : ''}`}
          title="List view"
        >
          <List size={13} />
        </button>
        <button
          type="button"
          onClick={() => onViewModeChange('grid')}
          className={`${flatToolbarButtonClass} ${viewMode === 'grid' ? 'text-white' : ''}`}
          title="Grid view"
        >
          <Grid3X3 size={13} />
        </button>
        <span className={flatToolbarSeparatorClass}>｜</span>

        <button
          type="button"
          onClick={onOpenUploadPicker}
          disabled={!canBrowse || actionDisabled}
          className={flatToolbarButtonClass}
          title="Upload files"
        >
          <Upload size={12} />
          Upload
        </button>

        <button
          type="button"
          onClick={onRefresh}
          disabled={!canBrowse || actionDisabled}
          className={flatToolbarButtonClass}
        >
          <RefreshCw size={12} className={loading || loadingMore ? 'animate-spin' : ''} />
          Refresh
        </button>

        <button
          type="button"
          onClick={onClose}
          className={flatToolbarButtonClass}
        >
          <ArrowLeft size={12} />
          Back
        </button>
      </div>
    </div>
  );
};
