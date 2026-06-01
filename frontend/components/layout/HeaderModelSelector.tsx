import React, { useMemo } from 'react';
import { Select } from 'antd';
import { Brain, BrainCircuit, Globe, Image as ImageIcon, Loader2, Server, Settings } from 'lucide-react';
import { AppMode, ModelConfig } from '../../types/types';
import { isMultimodalUnderstandingModel } from '../../utils/modelSuitability';
import { getModelUsage } from '../../utils/modelUsage';
import { getModelIcon } from './headerHelpers';
import { getHeaderSelectWidthCh } from './headerSelectSizing';

interface HeaderModelSelectorProps {
  isLoadingModels: boolean;
  isModelMenuOpen: boolean;
  setIsModelMenuOpen: (value: boolean) => void;
  activeModelConfig?: ModelConfig;
  hasActiveProfile: boolean;
  visibleModels: ModelConfig[];
  currentModelId: string;
  onModelSelect: (id: string) => void;
  onOpenSettings: (tab?: 'profiles' | 'editor') => void;
  appMode: AppMode;
}

export const getModelSelectorWidthCh = (
  models: ReadonlyArray<Pick<ModelConfig, 'id' | 'name'>>,
  fallbackLabel = 'Select Model'
) => {
  return getHeaderSelectWidthCh(
    models.map((model) => model.name || model.id),
    fallbackLabel
  );
};

const ModelCapabilities: React.FC<{ model: ModelConfig }> = ({ model }) => (
  <span className="ml-2 inline-flex items-center gap-1">
    {model.capabilities.search && <Globe size={12} className="text-blue-400" />}
    {model.capabilities.reasoning && <Brain size={12} className="text-purple-400" />}
    {model.capabilities.vision && isMultimodalUnderstandingModel(model) && (
      <ImageIcon size={12} className="text-emerald-400" />
    )}
    {model.capabilities.coding && <BrainCircuit size={12} className="text-amber-400" />}
  </span>
);

export const HeaderModelSelector: React.FC<HeaderModelSelectorProps> = ({
  isLoadingModels,
  isModelMenuOpen,
  setIsModelMenuOpen,
  activeModelConfig,
  hasActiveProfile,
  visibleModels,
  currentModelId,
  onModelSelect,
  onOpenSettings,
  appMode,
}) => {
  const ActiveIcon = activeModelConfig ? getModelIcon(activeModelConfig) : Loader2;
  const placeholder = hasActiveProfile ? 'Select Model' : 'No Config';
  const modelSelectorWidthCh = useMemo(
    () => getModelSelectorWidthCh(visibleModels, placeholder),
    [placeholder, visibleModels]
  );

  const options = useMemo(() => (
    visibleModels.map((model) => {
      const Icon = getModelIcon(model);
      const usage = getModelUsage(model);

      return {
        value: model.id,
        title: model.name || model.id,
        searchText: `${model.name || ''} ${model.id}`,
        label: (
          <div className="flex min-w-max items-start gap-3 py-1">
            <div
              className={`mt-0.5 rounded-lg p-2 ${
                currentModelId === model.id
                  ? 'bg-indigo-500 text-white'
                  : 'bg-slate-800 text-slate-400'
              }`}
            >
              <Icon size={18} />
            </div>
            <div className="min-w-max flex-1">
              <div className="flex min-w-max items-center">
                <span
                  className="whitespace-nowrap text-sm font-medium text-slate-100"
                  title={model.id}
                >
                  {model.name || model.id}
                </span>
                <ModelCapabilities model={model} />
              </div>
              <div className="truncate text-xs leading-tight text-slate-500" title={usage}>
                {usage}
              </div>
            </div>
          </div>
        ),
      };
    })
  ), [currentModelId, visibleModels]);

  return (
    <div
      data-testid="header-model-selector"
      className="flex w-fit min-w-0 max-w-full items-center gap-2"
    >
      <div className="shrink-0 rounded bg-indigo-500/10 p-1 text-indigo-400">
        {isLoadingModels ? (
          <Loader2 size={16} className="animate-spin text-slate-400" />
        ) : (
          <ActiveIcon size={16} />
        )}
      </div>
      <Select
        aria-label="选择模型"
        className="header-model-select max-w-full"
        style={{ width: `${modelSelectorWidthCh}ch` }}
        classNames={{ popup: { root: 'header-select-popup header-model-select-popup' } }}
        popupMatchSelectWidth={false}
        styles={{ popup: { root: { minWidth: `${modelSelectorWidthCh}ch` } } }}
        open={isModelMenuOpen}
        onOpenChange={setIsModelMenuOpen}
        value={activeModelConfig ? currentModelId : undefined}
        placeholder={placeholder}
        disabled={isLoadingModels || !hasActiveProfile}
        loading={isLoadingModels}
        showSearch
        options={options}
        optionFilterProp="searchText"
        optionLabelProp="title"
        onChange={(modelId) => onModelSelect(modelId)}
        getPopupContainer={(trigger) => trigger.parentElement || document.body}
        popupRender={(menu) => (
          <>
            {visibleModels.length === 0 ? (
              <div className="flex flex-col items-center gap-2 p-4 text-center text-sm text-slate-500">
                <Server size={24} className="opacity-50" />
                <p>
                  No compatible models found for this profile in <b>{appMode}</b> mode.
                </p>
                <button
                  type="button"
                  onClick={() => onOpenSettings('editor')}
                  className="text-xs text-indigo-400 hover:underline"
                >
                  Verify Config
                </button>
              </div>
            ) : (
              menu
            )}
            <div className="border-t border-slate-800 bg-slate-900 p-2">
              <button
                type="button"
                onClick={() => {
                  setIsModelMenuOpen(false);
                  onOpenSettings('profiles');
                }}
                className="flex w-full items-center justify-center gap-2 rounded-lg p-2 text-xs text-slate-400 transition-colors hover:bg-slate-800 hover:text-white"
              >
                <Settings size={14} />
                <span>Manage Active Models</span>
                <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] text-slate-400">
                  {visibleModels.length}
                </span>
              </button>
            </div>
          </>
        )}
      />
    </div>
  );
};

export default HeaderModelSelector;
