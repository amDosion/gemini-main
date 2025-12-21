
import { ModelConfig } from "../../../types/types";

const ZHIPU_DEFAULTS: ModelConfig[] = [
    {
        id: "glm-4-plus",
        name: "GLM-4 Plus",
        description: "Flagship model with strong overall capabilities.",
        capabilities: { vision: true, reasoning: false, coding: true, search: true }
    },
    {
        id: "glm-4-0520",
        name: "GLM-4",
        description: "High performance general model.",
        capabilities: { vision: true, reasoning: false, coding: true, search: true }
    },
    {
        id: "glm-4-air",
        name: "GLM-4 Air",
        description: "Cost-effective high speed model.",
        capabilities: { vision: false, reasoning: false, coding: true, search: true }
    },
    {
        id: "glm-4-flash",
        name: "GLM-4 Flash",
        description: "Free/Ultra-fast model.",
        capabilities: { vision: false, reasoning: false, coding: true, search: true }
    },
    {
        id: "cogview-3-plus",
        name: "CogView 3 Plus",
        description: "Image generation model.",
        capabilities: { vision: true, reasoning: false, coding: false, search: false }
    }
];

export async function getZhiPuModels(apiKey: string, baseUrl: string): Promise<ModelConfig[]> {
    if (!apiKey) return ZHIPU_DEFAULTS;
    
    // ZhiPu doesn't always have a clean /models endpoint that returns capability data.
    // We rely on the hardcoded list but could verify auth here.
    return ZHIPU_DEFAULTS;
}
