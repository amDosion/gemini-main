
import { ModelConfig } from "../../../../types";

const CAPABILITY_OVERRIDES: Record<string, Partial<ModelConfig['capabilities']>> = {
    'gemini-2.0-flash-thinking': { reasoning: true, search: false }, // Explicitly disable search for thinking models
    'gemini-2.5': { reasoning: true }, 
    'gemini-3-pro': { reasoning: true },
    'veo': { vision: true } 
};

export async function getGoogleModels(apiKey: string, baseUrl: string): Promise<ModelConfig[]> {
    const keyToUse = apiKey || process.env.API_KEY || '';
    if (!keyToUse) return [];

    try {
      let cleanUrl = baseUrl ? baseUrl.trim().replace(/\/$/, '') : '';
      const isOfficial = !cleanUrl || cleanUrl.includes('googleapis.com');

      // 2. Endpoint Construction
      const endpointsToTry: string[] = [];

      if (isOfficial) {
          // STRICT OFFICIAL ENDPOINT
          endpointsToTry.push(`https://generativelanguage.googleapis.com/v1beta/models?key=${keyToUse}`);
      } else {
          // Proxy Logic
          if (cleanUrl.endsWith('/v1beta') || cleanUrl.endsWith('/v1')) {
              endpointsToTry.push(`${cleanUrl}/models?key=${keyToUse}`);
          } else {
              endpointsToTry.push(`${cleanUrl}/v1beta/models?key=${keyToUse}`);
              endpointsToTry.push(`${cleanUrl}/models?key=${keyToUse}`);
          }
      }
      
      let response: Response | null = null;

      for (const endpoint of endpointsToTry) {
          try {
              const res = await fetch(endpoint, {
                  method: 'GET',
                  headers: {
                      'x-goog-api-key': keyToUse,
                      'Content-Type': 'application/json'
                  }
              });
              if (res.ok) {
                  response = res;
                  break;
              }
          } catch (e) {
              console.warn(`[GoogleProvider] Network error fetching models from ${endpoint}`, e);
          }
      }

      if (!response || !response.ok) {
          return [];
      }

      const data = await response.json();
      
      let apiModels: any[] = [];
      if (data.models) {
          apiModels = data.models; // Standard Google
      } else if (data.data) {
          apiModels = data.data; // OpenAI Wrapper / Proxy
      } else if (Array.isArray(data)) {
          apiModels = data; // Raw array
      }

      const configuredModels: ModelConfig[] = [];

      apiModels.forEach((model: any) => {
        // Normalize ID
        let modelId = model.id || model.name || '';
        if (modelId.startsWith('models/')) modelId = modelId.replace('models/', '');
        
        const supportedMethods: string[] = model.supportedGenerationMethods || [];
        
        if (supportedMethods.length > 0) {
             const canGen = supportedMethods.includes('generateContent') || supportedMethods.includes('generateVideos') || supportedMethods.includes('predict');
             if (!canGen) return; 
        }

        const displayName = model.displayName || modelId;

        const isMultimodal = modelId.includes('1.5') || modelId.includes('2.0') || modelId.includes('2.5') || modelId.includes('3.0') || modelId.includes('vision') || modelId.includes('image') || modelId.includes('imagen');
        const isLegacy = modelId.includes('1.0') || (modelId.includes('gemini-pro') && !modelId.includes('1.5'));
        
        const isThinking = modelId.includes('thinking') || modelId.includes('reasoning') || modelId.includes('2.5') || modelId.includes('3-pro') || modelId.includes('3.0');

        const supportsSearch = !isLegacy && !modelId.includes('imagen') && !modelId.includes('thinking');

        const capabilities = {
          vision: isMultimodal,
          search: supportsSearch,
          reasoning: isThinking,
          coding: !modelId.includes('imagen')
        };

        Object.entries(CAPABILITY_OVERRIDES).forEach(([key, overrides]) => {
          if (modelId.includes(key)) Object.assign(capabilities, overrides);
        });

        configuredModels.push({
          id: modelId,
          name: displayName,
          description: model.description || 'Google Model',
          capabilities: capabilities,
          baseModelId: modelId
        });
      });

      return configuredModels.sort((a, b) => {
          const score = (id: string) => {
              if (id.includes('gemini-3-pro')) return 100;
              if (id.includes('gemini-2.5-pro')) return 90;
              if (id.includes('2.5-flash-image')) return 11;
              if (id.includes('2.5-flash')) return 10;
              if (id.includes('thinking')) return 9;
              if (id.includes('imagen')) return 8;
              if (id.includes('veo')) return 1; 
              return 0;
          };
          return score(b.id) - score(a.id);
      });

    } catch (error) {
      console.error("Critical error in getGoogleModels", error);
      return [];
    }
}
