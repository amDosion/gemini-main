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
export const useLLMService = (_initData?: InitData, activeProfile?: ConfigProfile | null) => {
  // activeProfile 是唯一 source-of-truth；_initData 仅为保持调用方签名兼容而保留。
  useEffect(() => {
    if (activeProfile) {
      // protocol 后端可能返回任意字符串，需 narrow 到 ApiProtocol union
      const rawProtocol = activeProfile.protocol;
      const protocol: ApiProtocol | null =
        rawProtocol === 'google' || rawProtocol === 'openai' ? rawProtocol : null;
      llmService.setConfig(
        activeProfile.apiKey || '',
        activeProfile.baseUrl || '',
        protocol,
        activeProfile.providerId || ''
      );
    } else if (activeProfile === null) {
      // 显式 null = 用户未配置,清空 llmService
      llmService.setConfig('', '', null, '');
    }
  }, [activeProfile]);
};
