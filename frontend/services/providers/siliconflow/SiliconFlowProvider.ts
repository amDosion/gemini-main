
import { OpenAIProvider } from "../openai/OpenAIProvider";
import { ModelConfig } from "../../../types/types";
import { getSiliconFlowModels } from "./models";

export class SiliconFlowProvider extends OpenAIProvider {
    public id = 'siliconflow';

    public async getAvailableModels(apiKey: string, baseUrl: string): Promise<ModelConfig[]> {
        return getSiliconFlowModels(apiKey, baseUrl);
    }
    
    // In the future, we can override sendMessageStream here if SiliconFlow requires 
    // special handling for DeepSeek R1 reasoning tags (<think>) if they differ from standard OpenAI fields.
}
