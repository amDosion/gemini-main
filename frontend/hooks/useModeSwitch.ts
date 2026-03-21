
import { useCallback, Dispatch, SetStateAction } from 'react';
import { AppMode } from '../types/types';

interface UseModeSwitchProps {
  setAppMode: Dispatch<SetStateAction<AppMode>>;
}

interface UseModeSwitchReturn {
  handleModeSwitch: (mode: AppMode) => void;
}

/**
 * 模式切换 Hook
 * 只负责切换模式。
 * 具体模型过滤/选择由后端 + useModels 统一处理，避免前后端规则分叉。
 */
export const useModeSwitch = ({
  setAppMode
}: UseModeSwitchProps): UseModeSwitchReturn => {
  const handleModeSwitch = useCallback((mode: AppMode) => {
    setAppMode(mode);
  }, [setAppMode]);

  return { handleModeSwitch };
};
