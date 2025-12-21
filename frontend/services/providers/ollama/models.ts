
import { ModelConfig } from "../../../types/types";

export async function getOllamaModels(baseUrl: string): Promise<ModelConfig[]> {
    const defaultModels: ModelConfig[] = [
        {
            id: "llama3",
            name: "Llama 3 (Local)",
            description: "Meta's Llama 3 model running locally.",
            capabilities: { vision: false, reasoning: false, coding: true, search: false }
        }
    ];

    try {
        const cleanUrl = baseUrl.replace(/\/$/, '');
        // Ollama OpenAI-compat endpoint
        const response = await fetch(`${cleanUrl}/models`);
        
        if (!response.ok) return defaultModels;

        const data = await response.json();
        const models = data.data || [];

        if (models.length === 0) return defaultModels;

        return models.map((m: any) => {
            const id = m.id;
            const lowerId = id.toLowerCase();

            // Capability Heuristics
            const isVision = lowerId.includes('llava') || lowerId.includes('vision') || lowerId.includes('bakllava');
            const isReasoning = lowerId.includes('deepseek-r1') || lowerId.includes('reason');
            const isCoding = lowerId.includes('code') || lowerId.includes('sql') || lowerId.includes('codellama');

            // Formatted Name
            let name = id.split(':')[0]; // remove :latest tag
            name = name.charAt(0).toUpperCase() + name.slice(1);

            return {
                id: id,
                name: name,
                description: "Local Ollama Model",
                capabilities: {
                    vision: isVision,
                    reasoning: isReasoning,
                    coding: isCoding || true, // Assume most local models can code a bit
                    search: false
                }
            };
        }).sort((a: any, b: any) => a.name.localeCompare(b.name));

    } catch (e) {
        console.warn("Ollama connection failed. Ensure Ollama is running.", e);
        return defaultModels;
    }
}
