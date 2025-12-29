
import { OpenAIProvider } from "../openai/OpenAIProvider";
import { ModelConfig } from "../../../types/types";
import { getOllamaModels } from "./models";

export class OllamaProvider extends OpenAIProvider {
    public id = 'ollama';

    public async getAvailableModels(apiKey: string, baseUrl: string): Promise<ModelConfig[]> {
        // 传递 apiKey 用于远程 Ollama 服务认证
        return getOllamaModels(baseUrl, apiKey);
    }
}
