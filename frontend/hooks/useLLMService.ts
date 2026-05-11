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
  // ✅ B-5: 删除原 [initData] effect,只以 activeProfile 为单一 source-of-truth。
  // useSettings 已在 activeProfile 变化时同步 llmService.setConfig,这里仅保留一处。
  // _initData 保留参数以维持调用方签名兼容(App.tsx 可不必同步改)。
  useEffect(() => {
    if (activeProfile) {
      // 修 ts-reviewer MEDIUM：runtime check 替代 `as ApiProtocol` 强转
      // protocol 后端可能返回任意字符串，需要 narrow 到 ApiProtocol union
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
