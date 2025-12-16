
import { ModelConfig } from "../../../../types";

const MOONSHOT_MODELS: ModelConfig[] = [
    {
        id: "moonshot-v1-8k",
        name: "Moonshot V1 8K",
        description: "Efficient for short tasks and chats.",
        capabilities: { vision: false, reasoning: false, coding: true, search: true } // Kimi usually supports search via tools, but here we assume standard API
    },
    {
        id: "moonshot-v1-32k",
        name: "Moonshot V1 32K",
        description: "Medium context window for document reading.",
        capabilities: { vision: false, reasoning: false, coding: true, search: true }
    },
    {
        id: "moonshot-v1-128k",
        name: "Moonshot V1 128K",
        description: "Long context for massive document processing.",
        capabilities: { vision: false, reasoning: false, coding: true, search: true }
    }
];

export async function getMoonshotModels(apiKey: string, baseUrl: string): Promise<ModelConfig[]> {
    try {
        if (!apiKey) return MOONSHOT_MODELS;
        // Moonshot follows OpenAI standard
        const cleanUrl = baseUrl.replace(/\/$/, '');
        const response = await fetch(`${cleanUrl}/models`, {
            headers: { 'Authorization': `Bearer ${apiKey}` }
        });

        if (response.ok) {
            const data = await response.json();
            const models = data.data || [];
            if (models.length > 0) {
                 return models.map((m: any) => {
                     // Try to match metadata if we know it
                     const known = MOONSHOT_MODELS.find(km => km.id === m.id);
                     if (known) return known;
                     
                     return {
                         id: m.id,
                         name: m.id,
                         description: "Moonshot Model",
                         capabilities: { vision: false, reasoning: false, coding: true, search: false }
                     };
                 }).sort((a: any, b: any) => a.id.localeCompare(b.id));
            }
        }
    } catch (e) {
        console.warn("Moonshot fetch failed");
    }
    return MOONSHOT_MODELS;
}
