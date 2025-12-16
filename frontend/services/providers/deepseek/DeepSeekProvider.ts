
import { OpenAIProvider } from "../openai/OpenAIProvider";
import { ModelConfig } from "../../../../types";
import { getDeepSeekModels } from "./models";

export class DeepSeekProvider extends OpenAIProvider {
    public id = 'deepseek';

    public async getAvailableModels(apiKey: string, baseUrl: string): Promise<ModelConfig[]> {
        return getDeepSeekModels(apiKey, baseUrl);
    }
}
