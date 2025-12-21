
import { ModelConfig } from "../../../types/types";

const DEEPSEEK_MODELS: ModelConfig[] = [
    {
        id: "deepseek-chat",
        name: "DeepSeek V3",
        description: "General purpose large language model. Efficient and accurate.",
        capabilities: { vision: false, reasoning: false, coding: true, search: false }
    },
    {
        id: "deepseek-reasoner",
        name: "DeepSeek R1",
        description: "Reasoning-specialized model with Chain-of-Thought (CoT).",
        capabilities: { vision: false, reasoning: true, coding: true, search: false }
    }
];

export async function getDeepSeekModels(apiKey: string, baseUrl: string): Promise<ModelConfig[]> {
    // DeepSeek API /models endpoint usually returns these two. 
    // We can fetch to verify connectivity, but the list is stable.
    try {
        if (!apiKey) return DEEPSEEK_MODELS;
        
        const cleanUrl = baseUrl.replace(/\/$/, '');
        const response = await fetch(`${cleanUrl}/models`, {
            headers: { 'Authorization': `Bearer ${apiKey}` }
        });
        
        if (response.ok) {
            // Just verifying auth works, DeepSeek mostly exposes these two standard aliases
            return DEEPSEEK_MODELS;
        }
    } catch (e) {
        console.warn("DeepSeek fetch failed, using defaults");
    }
    return DEEPSEEK_MODELS;
}
