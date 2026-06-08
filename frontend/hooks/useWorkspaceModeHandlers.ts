import { useCallback } from 'react';

import { AppMode } from '../types/types';

export interface UseWorkspaceModeHandlersParams {
  appMode: AppMode;
  openWorkspaceModes: AppMode[];
  setOpenWorkspaceModes: React.Dispatch<React.SetStateAction<AppMode[]>>;
  setWorkspaceReloadKeys: React.Dispatch<React.SetStateAction<Partial<Record<AppMode, number>>>>;
  handleModeSwitch: (mode: AppMode) => void;
  selectLatestSessionForMode: (mode: AppMode) => boolean;
  refreshSessions: (options?: { force?: boolean }) => void | Promise<void>;
}

export interface WorkspaceModeHandlers {
  handleWorkspaceModeSelect: (mode: AppMode) => void;
  handleModeNavigationSelect: (mode: AppMode) => void;
  handleWorkspaceModesClose: (modes: AppMode[]) => void;
  handleWorkspaceModeClose: (mode: AppMode) => void;
  handleWorkspaceModeReload: (mode: AppMode) => void;
}

/**
 * Workspace-tab 模式操作 handler 集合。
 *
 * 1:1 抽离自 `App.tsx`（< 800 行合规拆分）。仅封装 handler 逻辑；
 * 所有 useState/useEffect 仍由 App.tsx 持有，本 hook 通过参数接收 state 与 setter。
 */
export const useWorkspaceModeHandlers = (
  params: UseWorkspaceModeHandlersParams
): WorkspaceModeHandlers => {
  const {
    appMode,
    openWorkspaceModes,
    setOpenWorkspaceModes,
    setWorkspaceReloadKeys,
    handleModeSwitch,
    selectLatestSessionForMode,
    refreshSessions,
  } = params;

  const openWorkspaceMode = useCallback(
    (mode: AppMode) => {
      setOpenWorkspaceModes((current) => (current.includes(mode) ? current : [...current, mode]));
    },
    [setOpenWorkspaceModes]
  );

  const handleWorkspaceModeSelect = useCallback(
    (mode: AppMode) => {
      openWorkspaceMode(mode);
      handleModeSwitch(mode);
    },
    [handleModeSwitch, openWorkspaceMode]
  );

  const handleModeNavigationSelect = useCallback(
    (mode: AppMode) => {
      openWorkspaceMode(mode);
      const hasCachedLatest = selectLatestSessionForMode(mode);
      handleModeSwitch(mode);
      if (mode === appMode && !hasCachedLatest) {
        refreshSessions();
      }
    },
    [appMode, handleModeSwitch, openWorkspaceMode, refreshSessions, selectLatestSessionForMode]
  );

  const handleWorkspaceModesClose = useCallback(
    (modes: AppMode[]) => {
      const closeSet = new Set(modes);
      if (openWorkspaceModes.length <= 1 || closeSet.size === 0) {
        return;
      }

      const nextOpenModes = openWorkspaceModes.filter((item) => !closeSet.has(item));
      if (nextOpenModes.length === 0 || nextOpenModes.length === openWorkspaceModes.length) {
        return;
      }

      setOpenWorkspaceModes(nextOpenModes);

      if (closeSet.has(appMode)) {
        const modeIndex = openWorkspaceModes.indexOf(appMode);
        const previousOpenMode = [...openWorkspaceModes.slice(0, modeIndex)]
          .reverse()
          .find((item) => !closeSet.has(item));
        const nextOpenMode = openWorkspaceModes
          .slice(modeIndex + 1)
          .find((item) => !closeSet.has(item));
        const nextActiveMode = previousOpenMode || nextOpenMode || nextOpenModes[0] || 'chat';
        handleModeSwitch(nextActiveMode);
      }
    },
    [appMode, handleModeSwitch, openWorkspaceModes, setOpenWorkspaceModes]
  );

  const handleWorkspaceModeClose = useCallback(
    (mode: AppMode) => {
      handleWorkspaceModesClose([mode]);
    },
    [handleWorkspaceModesClose]
  );

  const handleWorkspaceModeReload = useCallback(
    (mode: AppMode) => {
      setWorkspaceReloadKeys((current) => ({
        ...current,
        [mode]: (current[mode] || 0) + 1,
      }));

      if (mode === appMode) {
        refreshSessions({ force: true });
      }
    },
    [appMode, refreshSessions, setWorkspaceReloadKeys]
  );

  return {
    handleWorkspaceModeSelect,
    handleModeNavigationSelect,
    handleWorkspaceModesClose,
    handleWorkspaceModeClose,
    handleWorkspaceModeReload,
  };
};
