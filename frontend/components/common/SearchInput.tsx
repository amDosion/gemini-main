import React from 'react';
import { Search, X } from 'lucide-react';

interface SearchInputProps {
  value: string;
  onChange: (value: string) => void;
  onSearch: () => void;
  onClear: () => void;
  placeholder?: string;
  className?: string;
}

export const SearchInput: React.FC<SearchInputProps> = ({
  value,
  onChange,
  onSearch,
  onClear,
  placeholder = 'Search...',
  className = '',
}) => {
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      onSearch();
    } else if (e.key === 'Escape') {
      onClear();
    }
  };

  return (
    <div className={`relative ${className}`}>
      <input
        type="text"
        id="sidebar-search-input"
        name="sidebar-search-input"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        className="w-full pl-4 pr-16 py-2.5 bg-slate-800 border border-slate-700 rounded-lg text-white text-sm placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all"
        aria-label={placeholder}
      />
      <div className="absolute right-1 top-1/2 -translate-y-1/2 flex items-center gap-1">
        {value && (
          <button
            onClick={onClear}
            className="p-1.5 text-slate-500 hover:text-white transition-colors rounded hover:bg-slate-700"
            aria-label="Clear search"
            title="Clear"
          >
            <X size={14} />
          </button>
        )}
        <button
          onClick={onSearch}
          className="p-1.5 text-slate-500 hover:text-indigo-400 transition-colors rounded hover:bg-slate-700"
          aria-label="Search"
          title="Search"
        >
          <Search size={16} />
        </button>
      </div>
    </div>
  );
};
