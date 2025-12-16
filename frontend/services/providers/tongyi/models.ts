
import { ModelConfig } from "../../../../types";

// --- Metadata Registry for DashScope Models ---
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

const TONGYI_MODEL_REGISTRY: Record<string, ModelMetadata> = {
    // --- Deep Research ---
    "qwen-deep-research": {
        name: "Qwen Deep Research",
        description: "Specialized model for deep web research and complex query resolution.",
        capabilities: { vision: false, reasoning: true, coding: true, search: true },
        score: 110
    },

    // --- Deep Thinking (Reasoning) ---
    "qwq-32b": {
        name: "Qwen QwQ 32B",
        description: "Reasoning-focused model with Deep Thinking capabilities.",
        capabilities: { vision: false, reasoning: true, coding: true, search: false },
        score: 105
    },

    // --- Qwen Text Series ---
    "qwen-max": {
        name: "Qwen Max",
        description: "Alibaba's most capable large model. Excellent at complex reasoning.",
        capabilities: { vision: false, reasoning: false, coding: true, search: true },
        score: 100
    },
    "qwen-plus": {
        name: "Qwen Plus",
        description: "Balanced performance and speed.",
        capabilities: { vision: false, reasoning: false, coding: true, search: true },
        score: 90
    },
    "qwen-turbo": {
        name: "Qwen Turbo",
        description: "Fast and cost-effective.",
        capabilities: { vision: false, reasoning: false, coding: true, search: true },
        score: 80
    },

    // --- Qwen VL (Vision) Series ---
    "qwen-vl-max": {
        name: "Qwen VL Max",
        description: "State-of-the-art vision understanding. Supports VQA, OCR, Detection via prompts.",
        capabilities: { vision: true, reasoning: false, coding: true, search: false },
        score: 95
    },
    "qwen-vl-plus": {
        name: "Qwen VL Plus",
        description: "Balanced visual understanding model.",
        capabilities: { vision: true, reasoning: false, coding: true, search: false },
        score: 85
    },

    // --- Image Generation Models ---
    "wanx-v2": {
        name: "Wanx V2 (TongYi Wanxiang)",
        description: "Latest text-to-image model. High fidelity, diverse styles.",
        capabilities: { vision: true, reasoning: false, coding: false, search: false },
        score: 125
    },
    "qwen-image-plus": {
        name: "Qwen Image Plus",
        description: "Flagship image generation. Best for text/couplets & complex details.",
        capabilities: { vision: true, reasoning: false, coding: false, search: false },
        score: 120 
    },
    "wanx-v1": {
        name: "Wanx V1",
        description: "Legacy text-to-image model.",
        capabilities: { vision: true, reasoning: false, coding: false, search: false },
        score: 70
    },

    // --- Image Editing Models ---
    "wanx-v2.5-image-edit": {
        name: "Wanx V2.5 Edit (LoRA)",
        description: "Advanced image editing with Inpainting/Outpainting and LoRA style fusion.",
        capabilities: { vision: true, reasoning: false, coding: false, search: false },
        score: 115
    },
    "qwen-vl-image-edit": {
        name: "Qwen VL Edit",
        description: "Semantic image editing. Good for object removal and smart modification.",
        capabilities: { vision: true, reasoning: false, coding: false, search: false },
        score: 110
    }
};

export async function getTongYiModels(apiKey: string, baseUrl: string): Promise<ModelConfig[]> {
    if (!apiKey) return [];

    try {
        const cleanUrl = baseUrl.replace(/\/$/, '');
        const response = await fetch(`${cleanUrl}/models`, {
            headers: { 'Authorization': `Bearer ${apiKey}` }
        });

        if (!response.ok) {
            console.warn(`[DashScope] Failed to fetch models: ${response.status}`);
            return [];
        }

        const data = await response.json();
        const apiModels = data.data || [];

        let mappedModels: ModelConfig[] = apiModels.map((m: any) => {
            const id = m.id;
            
            // Check Registry
            if (TONGYI_MODEL_REGISTRY[id]) {
                const meta = TONGYI_MODEL_REGISTRY[id];
                return {
                    id: id,
                    name: meta.name,
                    description: meta.description,
                    capabilities: meta.capabilities,
                    baseModelId: id,
                    _score: meta.score
                };
            }

            const lowerId = id.toLowerCase();
            return {
                id: id,
                name: id,
                description: "DashScope Model",
                capabilities: {
                    vision: lowerId.includes('vl') || lowerId.includes('vision') || lowerId.includes('wanx') || lowerId.includes('image'),
                    reasoning: lowerId.includes('deepseek-r1') || lowerId.includes('qwq') || lowerId.includes('thinking'), 
                    coding: lowerId.includes('coder') || true,
                    search: false
                },
                baseModelId: id,
                _score: 0
            };
        });

        return mappedModels.sort((a: any, b: any) => {
            const scoreDiff = (b._score || 0) - (a._score || 0);
            if (scoreDiff !== 0) return scoreDiff;
            return a.id.localeCompare(b.id);
        });

    } catch (e) {
        console.error("[DashScope] Error fetching models", e);
        // Fallback: Return registry models if API fetch fails (common if list permission missing)
        return Object.entries(TONGYI_MODEL_REGISTRY).map(([id, meta]) => ({
            id: id,
            name: meta.name,
            description: meta.description,
            capabilities: meta.capabilities,
            baseModelId: id
        }));
    }
}
