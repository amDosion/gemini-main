
import { OpenAIProvider } from "../openai/OpenAIProvider";
import { ModelConfig } from "../../../types/types";
import { getOllamaModels } from "./models";

export class OllamaProvider extends OpenAIProvider {
    public id = 'ollama';

    public async getAvailableModels(apiKey: string, baseUrl: string): Promise<ModelConfig[]> {
        // Ollama usually doesn't need an API key, but we pass what we have
        return getOllamaModels(baseUrl);
    }
}
