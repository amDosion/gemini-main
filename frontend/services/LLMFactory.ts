
import { ApiProtocol } from '../../types';
import { ILLMProvider } from './providers/interfaces';
import { GoogleProvider } from './providers/google/GoogleProvider';
import { OpenAIProvider } from './providers/openai/OpenAIProvider';
import { DashScopeProvider } from './providers/tongyi/DashScopeProvider';
import { SiliconFlowProvider } from './providers/siliconflow/SiliconFlowProvider';
import { DeepSeekProvider } from './providers/deepseek/DeepSeekProvider';
import { MoonshotProvider } from './providers/moonshot/MoonshotProvider';
import { ZhiPuProvider } from './providers/zhipu/ZhiPuProvider';
import { OllamaProvider } from './providers/ollama/OllamaProvider';

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
    if (protocol === 'openai' && providerId !== 'tongyi' && providerId !== 'siliconflow' && providerId !== 'deepseek' && providerId !== 'moonshot' && providerId !== 'zhipu' && providerId !== 'ollama') {
        // Generic OpenAI Provider for custom proxies or Google-via-OpenAI
        provider = new OpenAIProvider();
    } else {
        // Explicit Provider Logic
        switch (providerId) {
            case 'google':
            case 'google-custom':
                // Double check protocol to be safe, though the if-block above handles 'openai' case
                if (protocol === 'openai') provider = new OpenAIProvider();
                else provider = new GoogleProvider();
                break;
            case 'tongyi':
                provider = new DashScopeProvider();
                break;
            case 'siliconflow':
                provider = new SiliconFlowProvider();
                break;
            case 'deepseek':
                provider = new DeepSeekProvider();
                break;
            case 'moonshot':
                provider = new MoonshotProvider();
                break;
            case 'zhipu':
                provider = new ZhiPuProvider();
                break;
            case 'ollama':
                provider = new OllamaProvider();
                break;
            case 'openai':
            case 'custom':
                provider = new OpenAIProvider();
                break;
            default:
                // Dynamic Fallback
                if (protocol === 'google') {
                    provider = new GoogleProvider();
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
