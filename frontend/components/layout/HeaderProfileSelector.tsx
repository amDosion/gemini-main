import React, { useMemo, useState } from 'react';
import { Select } from 'antd';
import { PlusCircle, Settings } from 'lucide-react';
import { ConfigProfile } from '../../services/db';
import { getProviderIcon } from './headerHelpers';
import { getHeaderSelectWidthCh } from './headerSelectSizing';

interface HeaderProfileSelectorProps {
  profiles: ConfigProfile[];
  activeProfileId: string | null;
  onActivateProfile: (id: string) => void | Promise<void>;
  onOpenSettings: (tab?: 'profiles' | 'editor') => void;
  onError: (message: string) => void;
}

const PROFILE_SELECTOR_PLACEHOLDER = 'Setup Required';

export const getProfileSelectorWidthCh = (
  profiles: ReadonlyArray<Pick<ConfigProfile, 'name'>>,
  fallbackLabel = PROFILE_SELECTOR_PLACEHOLDER
) => {
  return getHeaderSelectWidthCh(
    profiles.map((profile) => profile.name),
    fallbackLabel
  );
};

export const HeaderProfileSelector: React.FC<HeaderProfileSelectorProps> = ({
  profiles,
  activeProfileId,
  onActivateProfile,
  onOpenSettings,
  onError,
}) => {
  const [isActivating, setIsActivating] = useState(false);
  const profileSelectorWidthCh = useMemo(
    () => getProfileSelectorWidthCh(profiles),
    [profiles]
  );

  const options = useMemo(() => (
    profiles.map((profile) => ({
      value: profile.id,
      title: profile.name,
      searchText: `${profile.name} ${profile.providerId}`,
      label: (
        <div className="flex min-w-max items-center gap-3">
          <div className="shrink-0 rounded bg-slate-800 p-1 text-slate-400">
            {getProviderIcon(profile.providerId)}
          </div>
          <div className="flex min-w-max flex-col">
            <span className="whitespace-nowrap text-sm font-medium text-slate-100">
              {profile.name}
            </span>
            <span className="whitespace-nowrap font-mono text-[10px] text-slate-500">
              {profile.providerId} • {profile.cachedModelCount ?? '?'} models
            </span>
          </div>
        </div>
      ),
    }))
  ), [profiles]);

  const handleChange = async (profileId: string) => {
    setIsActivating(true);
    try {
      await onActivateProfile(profileId);
    } catch {
      onError('切换提供商失败，请重试');
    } finally {
      setIsActivating(false);
    }
  };

  return (
    <div className="mr-1 hidden w-fit min-w-0 shrink-0 border-r border-slate-700/50 pr-3 md:block">
      <Select
        aria-label="选择提供商"
        className="header-provider-select max-w-full"
        style={{ width: `${profileSelectorWidthCh}ch` }}
        classNames={{ popup: { root: 'header-select-popup' } }}
        popupMatchSelectWidth={false}
        styles={{ popup: { root: { minWidth: `${profileSelectorWidthCh}ch` } } }}
        value={activeProfileId || undefined}
        placeholder={PROFILE_SELECTOR_PLACEHOLDER}
        loading={isActivating}
        disabled={isActivating}
        options={options}
        optionFilterProp="searchText"
        optionLabelProp="title"
        showSearch
        onChange={handleChange}
        getPopupContainer={(trigger) => trigger.parentElement || document.body}
        popupRender={(menu) => (
          <>
            <div className="border-b border-slate-800 px-3 py-2 text-xs font-bold uppercase tracking-wider text-slate-500">
              Saved Configurations
            </div>
            {menu}
            <div className="border-t border-slate-800 bg-slate-900 p-2">
              <button
                type="button"
                onClick={() => onOpenSettings('editor')}
                className="mb-1 flex w-full items-center justify-center gap-2 rounded-lg p-2 text-xs text-indigo-300 transition-colors hover:bg-slate-800 hover:text-indigo-200"
              >
                <PlusCircle size={14} />
                Add Configuration
              </button>
              <button
                type="button"
                onClick={() => onOpenSettings('profiles')}
                className="flex w-full items-center justify-center gap-2 rounded-lg p-2 text-xs text-slate-400 transition-colors hover:bg-slate-800 hover:text-white"
              >
                <Settings size={14} />
                Manage Configurations
              </button>
            </div>
          </>
        )}
        notFoundContent={
          <div className="px-3 py-4 text-center text-xs text-slate-500">
            No profiles found.
          </div>
        }
      />
    </div>
  );
};

export default HeaderProfileSelector;
