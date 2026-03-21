import React, { useEffect, useMemo, useState } from 'react';

interface CloudStoragePaginationFooterProps {
  filteredItemCount: number;
  loadedItemCount: number;
  displayTotalItemCount: number;
  directoryTotalItemCount: number;
  isFilteringLocally: boolean;
  currentPage: number;
  totalPages: number;
  pageSize: number;
  loading?: boolean;
  onPageSizeChange: (pageSize: number) => void;
  onPageChange: (page: number) => void;
  onPrevPage: () => void;
  onNextPage: () => void;
}

const PAGE_SIZE_OPTIONS = [50, 100, 150, 200];

const buildVisiblePageItems = (currentPage: number, totalPages: number): Array<number | string> => {
  if (totalPages <= 7) {
    return Array.from({ length: totalPages }, (_, index) => index + 1);
  }

  const pages = new Set<number>([1, totalPages, currentPage - 1, currentPage, currentPage + 1]);

  if (currentPage <= 4) {
    [2, 3, 4, 5].forEach((page) => pages.add(page));
  }

  if (currentPage >= totalPages - 3) {
    [totalPages - 4, totalPages - 3, totalPages - 2, totalPages - 1].forEach((page) => pages.add(page));
  }

  const sortedPages = [...pages].filter((page) => page >= 1 && page <= totalPages).sort((left, right) => left - right);
  const items: Array<number | string> = [];

  sortedPages.forEach((page, index) => {
    const previousPage = sortedPages[index - 1];
    if (previousPage && page - previousPage > 1) {
      items.push(`ellipsis-${previousPage}-${page}`);
    }
    items.push(page);
  });

  return items;
};

export const CloudStoragePaginationFooter: React.FC<CloudStoragePaginationFooterProps> = ({
  filteredItemCount,
  loadedItemCount,
  displayTotalItemCount,
  directoryTotalItemCount,
  isFilteringLocally,
  currentPage,
  totalPages,
  pageSize,
  loading = false,
  onPageSizeChange,
  onPageChange,
  onPrevPage,
  onNextPage
}) => {
  const [pageInput, setPageInput] = useState(String(currentPage));

  useEffect(() => {
    setPageInput(String(currentPage));
  }, [currentPage]);

  const visiblePageItems = useMemo(
    () => buildVisiblePageItems(currentPage, totalPages),
    [currentPage, totalPages]
  );

  const activeTotal = displayTotalItemCount;
  const rangeStart = activeTotal === 0 ? 0 : (currentPage - 1) * pageSize + 1;
  const rangeEnd = Math.min(activeTotal, currentPage * pageSize);
  const summaryText = isFilteringLocally
    ? `Showing ${rangeStart}-${rangeEnd} of ${filteredItemCount} filtered item(s) · ${directoryTotalItemCount} total · ${loadedItemCount} loaded`
    : `Showing ${rangeStart}-${rangeEnd} of ${displayTotalItemCount} item(s) · ${loadedItemCount} loaded`;

  const commitPageInput = () => {
    const nextPage = Number.parseInt(pageInput, 10);
    if (!Number.isFinite(nextPage)) {
      setPageInput(String(currentPage));
      return;
    }

    const safePage = Math.min(totalPages, Math.max(1, nextPage));
    setPageInput(String(safePage));

    if (safePage !== currentPage) {
      onPageChange(safePage);
    }
  };

  return (
    <div className="px-4 md:px-6 py-2.5 border-t border-slate-800 bg-slate-900/40 flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
      <div className="text-xs text-slate-400">
        {summaryText} · Page {currentPage} of {totalPages}
      </div>
      <div className="flex flex-wrap items-center gap-2 xl:justify-end">
        <label className="flex items-center gap-2 text-xs text-slate-400">
          <span>Items / page</span>
          <select
            value={pageSize}
            onChange={(event) => onPageSizeChange(Number(event.target.value))}
            disabled={loading}
            className="px-2 py-1 rounded-md border border-slate-700 bg-slate-900 text-xs text-slate-300 focus:outline-none"
            title="Items per page"
          >
            {PAGE_SIZE_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option} / page
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          onClick={onPrevPage}
          disabled={loading || currentPage <= 1}
          className="px-2.5 py-1 rounded-md border border-slate-700 text-xs text-slate-300 hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Prev
        </button>
        <div className="flex flex-wrap items-center gap-1">
          {visiblePageItems.map((item) => {
            if (typeof item !== 'number') {
              return (
                <span key={item} className="px-1.5 text-xs text-slate-500">
                  ...
                </span>
              );
            }

            const isActive = item === currentPage;
            return (
              <button
                key={item}
                type="button"
                onClick={() => onPageChange(item)}
                disabled={loading}
                aria-current={isActive ? 'page' : undefined}
                className={`min-w-8 px-2.5 py-1 rounded-md border text-xs transition-colors ${
                  isActive
                    ? 'border-slate-200 bg-slate-200 text-slate-950'
                    : 'border-slate-700 text-slate-300 hover:bg-slate-800'
                }`}
              >
                {item}
              </button>
            );
          })}
        </div>
        <button
          type="button"
          onClick={onNextPage}
          disabled={loading || currentPage >= totalPages}
          className="px-2.5 py-1 rounded-md border border-slate-700 text-xs text-slate-300 hover:bg-slate-800 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Next
        </button>
        <div className="flex items-center gap-2 text-xs text-slate-400">
          <span>Go to page</span>
          <input
            type="number"
            min={1}
            max={totalPages}
            inputMode="numeric"
            value={pageInput}
            onChange={(event) => setPageInput(event.target.value)}
            onBlur={commitPageInput}
            disabled={loading}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                event.preventDefault();
                commitPageInput();
              }
            }}
            className="w-16 px-2 py-1 rounded-md border border-slate-700 bg-slate-900 text-xs text-slate-300 focus:outline-none"
            aria-label="Go to page"
          />
          <button
            type="button"
            onClick={commitPageInput}
            disabled={loading}
            className="px-2.5 py-1 rounded-md border border-slate-700 text-xs text-slate-300 hover:bg-slate-800"
          >
            Go
          </button>
        </div>
      </div>
    </div>
  );
};
