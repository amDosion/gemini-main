import React from 'react';
import { Brain, Check, CheckCircle2, Code, Eye, Image as ImageIcon, Search } from 'lucide-react';
import { getModelUsage, type ModelUsageSource } from '../../../utils/modelUsage';

export { getModelUsage } from '../../../utils/modelUsage';

export interface SelectableModel extends ModelUsageSource {}

interface ModelSelectionPanelProps<T extends SelectableModel> {
  models: T[];
  selectedModelIds: Set<string> | string[];
  onToggleModel: (modelId: string) => void;
  onSelectAll: () => void;
  onSelectNone: () => void;
  helperText?: string;
  testIdPrefix?: string;
}

export function ModelSelectionPanel<T extends SelectableModel>({
  models,
  selectedModelIds,
  onToggleModel,
  onSelectAll,
  onSelectNone,
  helperText = 'Check models to include in the dropdown.',
  testIdPrefix = 'settings-model',
}: ModelSelectionPanelProps<T>) {
  const selectedIds = selectedModelIds instanceof Set
    ? selectedModelIds
    : new Set(selectedModelIds);

  return (
    <div className="bg-slate-900/30 rounded-xl border border-slate-800 flex flex-col mt-2">
      <div className="p-2 bg-slate-900/50 border-b border-slate-800 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2 text-green-400 px-1">
          <CheckCircle2 size={14} />
          <span className="text-xs font-medium">Verified</span>
        </div>
        <div className="flex items-center gap-2 md:gap-1.5 flex-wrap">
          <button
            type="button"
            onClick={onSelectAll}
            className="text-xs bg-slate-800 hover:bg-slate-700 px-3 py-1.5 md:px-2 md:py-0.5 rounded text-slate-300 transition-colors border border-slate-700"
          >
            Select All
          </button>
          <button
            type="button"
            onClick={onSelectNone}
            className="text-xs bg-slate-800 hover:bg-slate-700 px-3 py-1.5 md:px-2 md:py-0.5 rounded text-slate-300 transition-colors border border-slate-700"
          >
            Select None
          </button>
          <span className="text-xs text-slate-500 ml-1 border-l border-slate-700 pl-2">
            {models.length} Models
          </span>
        </div>
      </div>

      {helperText && (
        <div className="bg-slate-950/30 p-2 text-xs text-slate-500 border-b border-slate-800/50 shrink-0">
          {helperText}
        </div>
      )}

      <div className="w-full p-3 md:p-2 overflow-y-auto">
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2 md:gap-1 w-full">
          {models.map((model) => {
            const isSelected = selectedIds.has(model.id);
            const usage = getModelUsage(model);
            const isImageLike = model.id.toLowerCase().includes('image') ||
              model.id.toLowerCase().includes('imagen') ||
              model.id.toLowerCase().includes('veo');

            return (
              <button
                type="button"
                key={model.id}
                data-testid={`${testIdPrefix}-card-${model.id}`}
                aria-pressed={isSelected}
                onClick={() => onToggleModel(model.id)}
                className={`flex w-full min-h-[54px] items-center gap-2 p-2 md:p-1.5 rounded-md cursor-pointer transition-colors border text-left ${
                  isSelected
                    ? 'bg-indigo-600/10 border-indigo-500/55 hover:bg-indigo-600/15 shadow-[inset_0_0_0_1px_rgba(99,102,241,0.16)]'
                    : 'bg-slate-900/80 border-slate-700/70 hover:bg-slate-800/90 hover:border-indigo-500/35'
                }`}
              >
                <div
                  className={`w-3.5 h-3.5 rounded-[3px] border flex items-center justify-center transition-colors shrink-0 ${
                    isSelected
                      ? 'bg-indigo-500 border-indigo-400 text-white'
                      : 'border-slate-500 bg-slate-950/60'
                  }`}
                >
                  {isSelected && <Check size={10} />}
                </div>

                <div className="min-w-0 flex-1 overflow-hidden">
                  <div className={`text-xs md:text-[11px] font-medium truncate leading-tight flex items-center gap-1 ${
                    isSelected ? 'text-indigo-50' : 'text-slate-200'
                  }`}>
                    {model.id}
                    {isImageLike && (
                      <ImageIcon size={10} className="text-indigo-400 shrink-0" />
                    )}
                  </div>

                  <div
                    data-testid={`${testIdPrefix}-meta-${model.id}`}
                    className="mt-1 flex min-w-0 items-center gap-1.5 overflow-hidden whitespace-nowrap"
                  >
                    <span className={`text-[10px] leading-none truncate ${
                      isSelected ? 'text-indigo-200' : 'text-slate-400'
                    }`}>
                      {usage}
                    </span>
                    <span className={`text-[9px] leading-none px-1.5 py-0.5 rounded border shrink-0 ${
                      isSelected
                        ? 'border-indigo-500/45 text-indigo-100 bg-indigo-950/40'
                        : 'border-slate-600/80 text-slate-300 bg-slate-950/50'
                    }`}>
                      {isSelected ? '已选择' : '未选择'}
                    </span>
                    {model.capabilities && (
                      <span className="flex items-center gap-1 shrink-0">
                        {model.capabilities.vision && (
                          <span title="Vision">
                            <Eye size={9} className="text-blue-400" />
                          </span>
                        )}
                        {model.capabilities.search && (
                          <span title="Search">
                            <Search size={9} className="text-cyan-400" />
                          </span>
                        )}
                        {model.capabilities.reasoning && (
                          <span title="Reasoning">
                            <Brain size={9} className="text-violet-400" />
                          </span>
                        )}
                        {model.capabilities.coding && (
                          <span title="Coding">
                            <Code size={9} className="text-sky-400" />
                          </span>
                        )}
                      </span>
                    )}
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
