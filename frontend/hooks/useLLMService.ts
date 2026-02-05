
import { useEffect } from 'react';
import { llmService } from '../services/llmService';
import { ApiProtocol } from '../types/types';
import { ConfigProfile } from '../services/db';

interface InitData {
  activeProfile?: ConfigProfile | null;
}

/**
 * LLM Service 初始化 Hook
 * 管理 llmService 的配置更新
 */
export const useLLMService = (
  initData?: InitData,
  activeProfile?: ConfigProfile | null
) => {
  // 从 initData 初始化 llmService
  useEffect(() => {
    if (initData?.activeProfile) {
      llmService.setConfig(
        initData.activeProfile.apiKey,
        initData.activeProfile.baseUrl,
        initData.activeProfile.protocol as ApiProtocol,
        initData.activeProfile.providerId
      );
    } else if (initData && !initData.activeProfile) {
      // 用户未配置，清空 llmService
      llmService.setConfig('', '', null, '');
    }
  }, [initData]);

  // 当 activeProfile 变化时更新 llmService
  useEffect(() => {
    if (activeProfile) {
      llmService.setConfig(
        activeProfile.apiKey || '',
        activeProfile.baseUrl || '',
        (activeProfile.protocol as ApiProtocol) || null,
        activeProfile.providerId || ''
      );
    }
  }, [activeProfile]);
};
