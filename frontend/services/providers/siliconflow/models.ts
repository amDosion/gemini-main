
import { ModelConfig } from "../../../types/types";

interface ModelMetadata {
    name: string;
    description: string;
    capabilities: {
        vision: boolean;
        reasoning: boolean;
        coding: boolean;
        search: boolean;
    };
    score?: number; 
}

const SILICONFLOW_MODEL_REGISTRY: Record<string, ModelMetadata> = {
    "deepseek-ai/DeepSeek-R1": {
        name: "DeepSeek R1",
        description: "Strongest open-source reasoning model with CoT.",
        capabilities: { vision: false, reasoning: true, coding: true, search: false },
        score: 100
    },
    "deepseek-ai/DeepSeek-R1-Distill-Llama-70B": {
        name: "DeepSeek R1 (Llama 70B)",
        description: "Distilled reasoning model, efficient and smart.",
        capabilities: { vision: false, reasoning: true, coding: true, search: false },
        score: 95
    },
    "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B": {
        name: "DeepSeek R1 (Qwen 32B)",
        description: "Distilled reasoning model, balanced speed/smarts.",
        capabilities: { vision: false, reasoning: true, coding: true, search: false },
        score: 94
    },
    "deepseek-ai/DeepSeek-V3": {
        name: "DeepSeek V3",
        description: "High performance general-purpose MoE model.",
        capabilities: { vision: false, reasoning: false, coding: true, search: false },
        score: 90
    },
    "Qwen/Qwen2.5-72B-Instruct": {
        name: "Qwen 2.5 72B",
        description: "Alibaba's flagship open model. Great at coding/math.",
        capabilities: { vision: false, reasoning: false, coding: true, search: false },
        score: 85
    },
    "Qwen/Qwen2.5-Coder-32B-Instruct": {
        name: "Qwen 2.5 Coder 32B",
        description: "Specialized for programming tasks.",
        capabilities: { vision: false, reasoning: false, coding: true, search: false },
        score: 84
    },
    "Qwen/Qwen2.5-7B-Instruct": {
        name: "Qwen 2.5 7B",
        description: "Fast, efficient general instruction model.",
        capabilities: { vision: false, reasoning: false, coding: true, search: false },
        score: 70
    },
    "Qwen/Qwen2-VL-72B-Instruct": {
        name: "Qwen2 VL 72B",
        description: "Visual understanding and reasoning.",
        capabilities: { vision: true, reasoning: false, coding: true, search: false },
        score: 88
    },
    "black-forest-labs/FLUX.1-schnell": {
        name: "Flux 1.0 Schnell",
        description: "Fast text-to-image generation.",
        capabilities: { vision: false, reasoning: false, coding: false, search: false },
        score: 60
    },
    "Pro/black-forest-labs/FLUX.1-schnell": {
        name: "Flux 1.0 Schnell (Pro)",
        description: "Fast text-to-image generation (Pro tier).",
        capabilities: { vision: false, reasoning: false, coding: false, search: false },
        score: 61
    },
    "stabilityai/stable-diffusion-3-medium": {
        name: "Stable Diffusion 3",
        description: "Text-to-image generation.",
        capabilities: { vision: false, reasoning: false, coding: false, search: false },
        score: 50
    }
};

function inferCapabilitiesFromId(id: string): ModelMetadata {
    const lower = id.toLowerCase();
    
    const isReasoning = lower.includes('r1') || lower.includes('reasoning') || lower.includes('thinking');
    const isVision = lower.includes('vl') || lower.includes('vision'); 
    const isImageGen = lower.includes('flux') || lower.includes('diffusion') || lower.includes('sdxl'); 
    const isCoding = lower.includes('code') || lower.includes('coder');

    let name = id;
    if (name.includes('/')) {
        name = name.split('/')[1];
    }

    return {
        name: name,
        description: isReasoning ? "Reasoning Model" : (isImageGen ? "Image Generation Model" : "General LLM"),
        capabilities: {
            vision: isVision,
            reasoning: isReasoning,
            coding: isCoding || (!isImageGen),
            search: false
        },
        score: 0
    };
}

export async function getSiliconFlowModels(apiKey: string, baseUrl: string): Promise<ModelConfig[]> {
    if (!apiKey) return [];

    try {
        const cleanUrl = baseUrl.replace(/\/$/, '');
        const response = await fetch(`${cleanUrl}/models`, {
            headers: { 
                'Authorization': `Bearer ${apiKey}`,
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            return [];
        }

        const data = await response.json();
        const apiModels = data.data || [];

        if (apiModels.length === 0) return [];

        return apiModels.map((m: any) => {
            const id = m.id;
            
            if (SILICONFLOW_MODEL_REGISTRY[id]) {
                const meta = SILICONFLOW_MODEL_REGISTRY[id];
                return {
                    id: id,
                    name: meta.name,
                    description: meta.description,
                    capabilities: meta.capabilities,
                    baseModelId: id,
                    _score: meta.score
                };
            }

            const inferred = inferCapabilitiesFromId(id);
            return {
                id: id,
                name: inferred.name,
                description: inferred.description,
                capabilities: inferred.capabilities,
                baseModelId: id,
                _score: 0
            };
        }).sort((a: any, b: any) => {
            const scoreDiff = (b._score || 0) - (a._score || 0);
            if (scoreDiff !== 0) return scoreDiff;
            return a.name.localeCompare(b.name);
        });

    } catch (e) {
        console.error("[SiliconFlow] Error fetching models", e);
        return [];
    }
}
