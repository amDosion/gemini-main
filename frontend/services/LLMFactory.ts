
import { ApiProtocol } from '../types/types';
import { ILLMProvider } from './providers/interfaces';
import { UnifiedProviderClient } from './providers/UnifiedProviderClient';
import { OpenAIProvider } from './providers/openai/OpenAIProvider';
import { DashScopeProvider } from './providers/tongyi/DashScopeProvider';

export class LLMFactory {
  // Cache by providerId (e.g., 'google', 'openai', 'deepseek', 'tongyi')
  private static instances: Map<string, ILLMProvider> = new Map();

  /**
   * Returns the appropriate provider instance.
   * @param protocol The API protocol (google, openai)
   * @param providerId The specific provider ID (e.g., 'deepseek', 'tongyi')
   */
  static getProvider(protocol: ApiProtocol, providerId: string): ILLMProvider {
    const cacheKey = `${providerId}_${protocol}`; // Include protocol in cache key

    if (this.instances.has(cacheKey)) {
        return this.instances.get(cacheKey)!;
    }

    let provider: ILLMProvider;

    // CRITICAL FIX: If protocol is OpenAI, we MUST use an OpenAI-compatible provider
    // even if the ID is 'google' (User using OpenAI-compatible proxy for Gemini).
    if (protocol === 'openai' && providerId !== 'tongyi') {
        // Generic OpenAI Provider for custom proxies or Google-via-OpenAI
        provider = new OpenAIProvider();
    } else {
        // Explicit Provider Logic
        switch (providerId) {
            case 'google':
            case 'google-custom':
                // ✅ Google 现在统一使用后端 SDK（UnifiedProviderClient）
                // 前端不再直接调用 Google SDK
                if (protocol === 'openai') provider = new OpenAIProvider();
                else provider = new UnifiedProviderClient('google');
                break;
            case 'tongyi':
                provider = new DashScopeProvider();
                break;
            case 'ollama':
            case 'siliconflow':
            case 'deepseek':
            case 'moonshot':
            case 'zhipu':
                // ✅ 这些 provider 通过后端统一处理（UnifiedProviderClient）
                provider = new UnifiedProviderClient(providerId);
                break;
            case 'openai':
            case 'custom':
                provider = new OpenAIProvider();
                break;
            default:
                // Dynamic Fallback
                if (protocol === 'google') {
                    // ✅ Google 统一使用后端 SDK
                    provider = new UnifiedProviderClient('google');
                } else {
                    provider = new OpenAIProvider();
                }
                break;
        }
    }

    this.instances.set(cacheKey, provider);
    return provider;
  }
}
