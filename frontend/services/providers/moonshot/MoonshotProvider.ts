
import { OpenAIProvider } from "../openai/OpenAIProvider";
import { ModelConfig } from "../../../../types";
import { getMoonshotModels } from "./models";

export class MoonshotProvider extends OpenAIProvider {
    public id = 'moonshot';

    public async getAvailableModels(apiKey: string, baseUrl: string): Promise<ModelConfig[]> {
        return getMoonshotModels(apiKey, baseUrl);
    }
}
