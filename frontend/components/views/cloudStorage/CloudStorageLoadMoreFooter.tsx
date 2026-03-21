import React from 'react';

interface CloudStorageLoadMoreFooterProps {
  loadingMore: boolean;
  onLoadMore: () => void;
}

export const CloudStorageLoadMoreFooter: React.FC<CloudStorageLoadMoreFooterProps> = ({
  loadingMore,
  onLoadMore
}) => {
  return (
    <div className="px-4 md:px-6 py-3 border-t border-slate-800 flex justify-center">
      <button
        type="button"
        onClick={onLoadMore}
        disabled={loadingMore}
        className="px-4 py-1.5 rounded-lg border border-slate-700 text-sm text-slate-200 hover:bg-slate-800 disabled:opacity-60 disabled:cursor-not-allowed"
      >
        {loadingMore ? 'Loading...' : 'Load More'}
      </button>
    </div>
  );
};
