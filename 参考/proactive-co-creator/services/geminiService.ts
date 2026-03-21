/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
*/

import { GoogleGenAI, GenerateContentResponse, GenerateImagesResponse, Modality, Type } from "@google/genai";
import { BeliefState, Clarification, Relationship, Candidate, GraphUpdate, Entity, Attribute } from '../types';

const API_KEY = process.env.API_KEY;

if (!API_KEY) {
  throw new Error("API_KEY environment variable not set");
}

// Global instance for standard calls
const ai = new GoogleGenAI({ apiKey: API_KEY });

export type StatusUpdateCallback = (message: string) => void;

// --- START: Retry Logic for API Calls ---
const isRetryableError = (error: any): boolean => {
  // Try to extract error message or stringify the error object
  const errorMessage = typeof error?.message === 'string' ? error.message : JSON.stringify(error);
  
  // The Gemini API can return 503 errors when overloaded. These are safe to retry.
  // We also want to retry on 500 (Internal Server Error) and RPC/XHR errors which are often transient.
  // We also retry on 429 (Resource Exhausted) as this often indicates temporary rate limiting.
  return (
    errorMessage.includes('"code":503') || 
    errorMessage.includes('"status":"UNAVAILABLE"') ||
    errorMessage.includes('"code":500') ||
    errorMessage.includes('"status":"UNKNOWN"') ||
    errorMessage.includes('Rpc failed') ||
    errorMessage.includes('xhr error') ||
    errorMessage.includes('502') || 
    errorMessage.includes('Bad Gateway') ||
    errorMessage.includes('504') ||
    errorMessage.includes('Gateway Timeout') ||
    errorMessage.includes('fetch failed') ||
    errorMessage.includes('"code":429') ||
    errorMessage.includes('429') ||
    errorMessage.includes('"status":"RESOURCE_EXHAUSTED"')
  );
};

const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

const withRetry = async <T>(
  fn: () => Promise<T>,
  retries = 3,
  initialDelay = 1000,
  onStatusUpdate?: StatusUpdateCallback,
  actionName: string = "Request"
): Promise<T> => {
  let lastError: any;
  let currentDelay = initialDelay;

  for (let i = 0; i < retries; i++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error;
      if (isRetryableError(error)) {
        const msg = `Connection unstable or rate limited during ${actionName}. Retrying (${i + 1}/${retries})...`;
        console.warn(msg);
        if (onStatusUpdate) onStatusUpdate(msg);

        await delay(currentDelay);
        currentDelay = currentDelay * 2 + Math.floor(Math.random() * 1000);
      } else {
        console.error("Encountered a non-retryable error:", error);
        throw error;
      }
    }
  }

  console.error("All retry attempts failed for the request.");
  throw lastError;
};
// --- END: Retry Logic for API Calls ---

/**
 * Generates the complete Belief Graph including Entities, Relationships, AND Rich Attributes in a single pass.
 */
export const parsePromptToBeliefGraph = async (prompt: string, mode: 'image' | 'story' | 'video', onStatusUpdate?: StatusUpdateCallback): Promise<BeliefState> => {
    console.log(`Generating Full Belief Graph (Structure + Attributes) for ${mode}:`, prompt);

    let specificInstructions = "";

    if (mode === 'image') {
        specificInstructions = `
        - **The Image Entity:** Always include an entity named "The Image". Required Attributes: weather, location, time of day, atmosphere, camera angle, image style.
        - **Human Subjects:** If an entity is human, include Attributes: age, gender, ethnicity, hair_style, clothing, expression, pose.
        - **Objects:** Include Attributes: color, material, shape, size, texture, lighting.
        `;
    } else if (mode === 'video') {
         specificInstructions = `
        - **The Video Entity:** Always include an entity named "The Video". Required Attributes: camera_movement, lighting, atmosphere, video_style, pacing, duration_feel.
        - **Subjects:** If an entity is active, include Attributes: movement, expression, action_speed, clothing.
        - **Setting:** Include Attributes: location, weather, time_of_day, ambience.
        `;
    } else {
        specificInstructions = `
        - **The Story Entity:** Always include an entity named "The Story". Required Attributes: genre, tone, narrative_perspective, pacing, central_conflict.
        - **Characters:** Include Attributes: personality, motivation, role, age, background, emotional_state.
        `;
    }

    const generationPrompt = `
    Analyze the prompt and generate a complete **Belief Graph** representing the scene or story.
    Identify all entities, their detailed attributes, and their relationships.

    Entity Types:
    - **Explicit Entities:** Clearly stated in the prompt (presence_in_prompt: True).
    - **Implicit Entities:** Entities not mentioned but logically necessary (presence_in_prompt: False). Limit to 2-3 key implicit entities.
    
    Attribute Rules:
    1.  **Existence:** For EVERY entity, you **MUST** include an attribute named 'existence' (value "true" or "false").
    2.  **Rich Attributes:** For every entity, generate 3-4 descriptive attributes based on these rules:
        ${specificInstructions}
    3.  **Values:** For EVERY attribute, provide 2-3 plausible alternative candidate values as a list of strings. The first value should be the most likely one.
    4.  **Inference:** If an attribute is not explicitly stated, infer a likely value and set "presence_in_prompt" to false.

    Relationships:
    - Identify logical relationships between entities (e.g., "holding", "next to", "part of").
    - Provide a label and alternatives (as strings).

    Input: { "prompt": "${prompt}" }
    OUTPUT JSON:`;

    // Optimization: Request arrays of strings instead of arrays of objects for values/alternatives to reduce token count.
    const attributeSchema = { 
        type: Type.OBJECT, 
        properties: { 
            name: { type: Type.STRING }, 
            presence_in_prompt: { type: Type.BOOLEAN }, 
            value: { type: Type.ARRAY, items: { type: Type.STRING } } 
        }, 
        required: ['name', 'presence_in_prompt', 'value'] 
    };
    
    const entitySchema = { 
        type: Type.OBJECT, 
        properties: { 
            name: { type: Type.STRING }, 
            presence_in_prompt: { type: Type.BOOLEAN }, 
            description: { type: Type.STRING }, 
            alternatives: { type: Type.ARRAY, items: { type: Type.STRING }, nullable: true }, 
            attributes: { type: Type.ARRAY, items: attributeSchema } 
        }, 
        required: ['name', 'presence_in_prompt', 'description', 'attributes'] 
    };
    
    const relationshipSchema = { 
        type: Type.OBJECT, 
        properties: { 
            source: { type: Type.STRING }, 
            target: { type: Type.STRING }, 
            label: { type: Type.STRING }, 
            alternatives: { type: Type.ARRAY, items: { type: Type.STRING }, nullable: true } 
        }, 
        required: ['source', 'target', 'label'] 
    };

    try {
        const response = await withRetry<GenerateContentResponse>(() => ai.models.generateContent({
            model: 'gemini-2.5-flash',
            contents: generationPrompt,
            config: {
                responseMimeType: "application/json",
                responseSchema: {
                    type: Type.OBJECT,
                    properties: {
                        entities: { type: Type.ARRAY, items: entitySchema },
                        relationships: { type: Type.ARRAY, items: relationshipSchema }
                    },
                    required: ['entities', 'relationships']
                }
            }
        }), 5, 2000, onStatusUpdate, "Belief Graph Generation");

        let jsonText = response.text.trim();
        if (jsonText.startsWith('```')) {
            jsonText = jsonText.replace(/^```(json)?/, '').replace(/```$/, '').trim();
        }

        const rawGraph = JSON.parse(jsonText);
        
        // Transform raw string arrays back to Candidate objects expected by the application
        const entities = rawGraph.entities.map((e: any) => ({
            ...e,
            alternatives: e.alternatives ? e.alternatives.map((s: string) => ({ name: s })) : [],
            attributes: e.attributes.map((a: any) => ({
                ...a,
                value: a.value.map((s: string) => ({ name: s }))
            }))
        }));

        const relationships = rawGraph.relationships.map((r: any) => ({
            ...r,
            alternatives: r.alternatives ? r.alternatives.map((s: string) => ({ name: s })) : []
        }));

        const graph: BeliefState = { entities, relationships, prompt };
        return graph;
    } catch (error) {
        console.error("Error generating belief graph:", error);
        return { entities: [], relationships: [], prompt };
    }
};

export const generateClarifications = async (prompt: string, askedQuestions: string[], mode: 'image' | 'story' | 'video', onStatusUpdate?: StatusUpdateCallback): Promise<Clarification[]> => {
    console.log(`Generating clarifications for ${mode} mode from prompt:`, prompt);
    
    const imagePrompt = `You are an expert in text-to-image prompting. Your goal is to help a user refine their prompt by asking clarifying questions.
First, reason about the user's prompt to identify entities, their attributes, and areas of visual uncertainty.
Then, generate questions that target these uncertainties to gather more specific visual details.

Focus on:
- Implicit entities (things not explicitly mentioned but likely to be in the scene).
- Vague attributes (e.g., if it says "a car", ask about the color or model).
- Ambiguous scene properties (e.g., location, time of day, style).`;

    const videoPrompt = `You are an expert in AI video generation prompting. Your goal is to help a user refine their prompt by asking clarifying questions.
First, reason about the user's prompt to identify the visual narrative, camera movement, and temporal dynamics.
Then, generate questions that target these uncertainties.

Focus on:
- Movement and Action (e.g., "How does the character move?", "Is the action fast or slow?").
- Camera Dynamics (e.g., "Should the camera zoom, pan, or stay static?").
- Atmosphere and Lighting changes over time.`;

    const storyPrompt = `You are a creative writing assistant. Your goal is to help a user develop their story idea by asking insightful clarifying questions based on their initial prompt.
First, reason about the prompt to identify potential characters, settings, plot points, and themes.
Then, generate questions that explore areas that would enrich the narrative.

Focus on:
- Character motivations or backstories.
- Plot developments or potential conflicts.
- Setting details that could influence the mood.
- The overall tone or theme of the story.`;

    let specificPrompt = imagePrompt;
    if (mode === 'story') specificPrompt = storyPrompt;
    if (mode === 'video') specificPrompt = videoPrompt;

    const finalPrompt = specificPrompt + `
    
Follow these instructions EXACTLY:
1.  **Quantity:** Generate EXACTLY 3 questions.
2.  **Clarity & Conciseness:** Questions must be very clear, concise, and direct.
3.  **Ease of Answering:** Questions should be easy for a human to answer, ideally by selecting from predefined choices.
4.  **Information Diversity:** The three questions MUST be different from each other and aim to collect information about distinct aspects.
5.  **Answer Choices:** For EACH question, provide a list of 3-5 plausible and distinct answer choices.
6.  **Avoid Repetition**: DO NOT ask any of the following questions (or questions semantically identical to them), as they have already been answered or rejected by the user:
    ${askedQuestions.map(q => `- "${q}"`).join('\n') || 'N/A'}

User Prompt: "${prompt}"

Return the output as a JSON array of objects, where each object has a 'question' and an 'options' array.`;

    try {
        const response = await withRetry<GenerateContentResponse>(() => ai.models.generateContent({
            model: 'gemini-2.5-flash',
            contents: finalPrompt,
            config: {
                // thinkingConfig removed
                responseMimeType: "application/json",
                responseSchema: {
                    type: Type.ARRAY,
                    items: {
                        type: Type.OBJECT,
                        properties: {
                            question: { type: Type.STRING },
                            options: { type: Type.ARRAY, items: { type: Type.STRING } }
                        },
                        required: ['question', 'options'],
                    },
                },
            },
        }), 5, 2000, onStatusUpdate, "Clarification Generation"); 

        let jsonText = response.text.trim();
        // Robust markdown stripping
        if (jsonText.startsWith('```')) {
            jsonText = jsonText.replace(/^```(json)?/, '').replace(/```$/, '').trim();
        }
        const clarifications = JSON.parse(jsonText);
        return clarifications as Clarification[];

    } catch (error) {
        console.error("Error generating clarifications with Gemini:", error);
        return [];
    }
};

export const refinePromptWithClarification = async (
  originalPrompt: string,
  question: string,
  answer: string
): Promise<string> => {
  // ... (No changes here, keeping existing implementation)
  console.log("Refining prompt with clarification:", { originalPrompt, question, answer });
  const prompt = `You are an expert prompt engineer.
Your task is to update a given prompt based on the answer to a clarification question.
Integrate the answer naturally and concisely into the prompt to improve the final output.
Do not add any extra explanations, just return the updated prompt string.

Original Prompt: "${originalPrompt}"
Clarification Question: "${question}"
User's Answer: "${answer}"

Updated Prompt:`;

  try {
    const response = await withRetry<GenerateContentResponse>(() => ai.models.generateContent({
        model: 'gemini-2.5-flash',
        contents: prompt,
    }));
    return response.text;
  } catch (error) {
    console.error("Error refining prompt:", error);
    return originalPrompt;
  }
};

export const refinePromptWithMultipleClarifications = async (
  originalPrompt: string,
  clarifications: { question: string; answer: string }[]
): Promise<string> => {
  // ... (No changes here, keeping existing implementation)
  console.log("Refining prompt with multiple clarifications:", { originalPrompt, clarifications });
  const prompt = `You are an expert prompt engineer.
Your task is to update a given prompt based on the user's answers to several clarification questions.
Integrate ALL the answers naturally and concisely into the prompt to improve the final output.
Do not add any extra explanations, just return the updated prompt string.

Original Prompt: "${originalPrompt}"

Clarifications:
${clarifications.map((c, i) => `${i+1}. Question: "${c.question}" Answer: "${c.answer}"`).join('\n')}

Updated Prompt:`;

  try {
    const response = await withRetry<GenerateContentResponse>(() => ai.models.generateContent({
        model: 'gemini-2.5-flash',
        contents: prompt,
    }));
    return response.text;
  } catch (error) {
    console.error("Error refining prompt:", error);
    return originalPrompt;
  }
};

export const refinePromptWithAllUpdates = async (
    originalPrompt: string,
    clarifications: { question: string; answer: string }[],
    graphUpdates: GraphUpdate[],
    onStatusUpdate?: StatusUpdateCallback
  ): Promise<string> => {
    console.log("Refining prompt with combined updates:", { originalPrompt, clarifications, graphUpdates });
  
    let updatesPromptSection = "";
    
    if (graphUpdates.length > 0) {
        const graphList = graphUpdates.map((u, i) => {
            if (u.type === 'attribute') {
                return `- For entity "${u.entity}", set attribute "${u.attribute}" to "${u.value}".`;
            } else {
                return `- Change relationship between "${u.source}" and "${u.target}" from "${u.oldLabel}" to "${u.newLabel}".`;
            }
        }).join('\n');
        updatesPromptSection += `\nSPECIFIC EDITS TO APPLY:\n${graphList}\n`;
    }
  
    if (clarifications.length > 0) {
        const qaList = clarifications.map((c, i) => `- User Answer to "${c.question}": "${c.answer}"`).join('\n');
        updatesPromptSection += `\nNEW INFORMATION FROM Q&A:\n${qaList}\n`;
    }
  
    const prompt = `You are an expert prompt engineer. Your goal is to rewrite the prompt to seamlessly incorporate specific user edits while strictly preserving all other existing details.
    
  Original Prompt: "${originalPrompt}"
  
  ${updatesPromptSection}
  
  Instructions:
  1.  **Integrate Attributes:** When an attribute is set (e.g., "color" to "blue"), ensure the entity is explicitly described with that attribute in the narrative.
  2.  **Update Relationships:** If a relationship changes, rewrite the interaction between the entities to reflect the new state.
  3.  **Incorporate Answers:** Treat user answers from clarifications as definitive facts and weave them into the scene.
  4.  **Preserve Context:** CRITICAL: Do NOT remove, summarize, or condense any existing details, entities, or stylistic elements from the "Original Prompt". The goal is accretion and modification, not summarization. Only remove details if they are explicitly contradicted by the edits.
  5.  **Exclusion:** CRITICAL: If an edit sets "existence" or "existence_in_image" to "false" (or "Absent"), you MUST remove that entity and its related descriptions entirely.
  6.  **Style:** Maintain the original tone (e.g., if it's a story, keep it narrative; if an image prompt, keep it descriptive).
  
  Do not add any extra explanations, just return the updated prompt string.
  
  Updated Prompt:`;
  
    try {
      const response = await withRetry<GenerateContentResponse>(() => ai.models.generateContent({
        model: 'gemini-2.5-flash',
        contents: prompt,
      }), 3, 1000, onStatusUpdate, "Prompt Refinement");
      return response.text;
    } catch (error) {
      console.error("Error refining prompt with all updates:", error);
      return originalPrompt;
    }
  };

export const generateImagesFromPrompt = async (prompt: string, onStatusUpdate?: StatusUpdateCallback): Promise<string[]> => {
    console.log("Generating images for prompt:", prompt);
    
    // Helper to generate one image using gemini-2.5-flash-image
    const generateOne = async (): Promise<string | null> => {
        try {
            const response = await withRetry<GenerateContentResponse>(() => ai.models.generateContent({
                model: 'gemini-2.5-flash-image',
                contents: {
                    parts: [
                        { text: prompt }
                    ]
                },
                config: {
                    imageConfig: {
                        aspectRatio: "1:1",
                    }
                }
            }), 3, 2000, onStatusUpdate, "Image Generation"); // Increased initial delay
            
            if (response.candidates && response.candidates[0].content && response.candidates[0].content.parts) {
                for (const part of response.candidates[0].content.parts) {
                    if (part.inlineData) {
                        return `data:image/png;base64,${part.inlineData.data}`;
                    }
                }
            }
            return null;
        } catch (err) {
            console.warn("Single image generation failed:", err);
            return null;
        }
    };

    // Execute multiple requests to ensure we get 4 images
    let images: string[] = [];
    let attempts = 0;
    const maxAttempts = 2; // Allow one retry pass for missing images

    while (images.length < 4 && attempts < maxAttempts) {
        const needed = 4 - images.length;
        if (needed === 0) break;
        
        console.log(`Generating ${needed} images, attempt ${attempts + 1}`);
        if (attempts > 0 && onStatusUpdate) {
             onStatusUpdate(`Generating remaining images... Attempt ${attempts + 1}`);
        }
        
        const promises = Array(needed).fill(null).map(() => generateOne());
        const results = await Promise.all(promises);
        
        // Filter out any nulls from failed requests
        const newImages = results.filter((img): img is string => img !== null);
        images = [...images, ...newImages];
        
        attempts++;
    }

    if (images.length === 0) {
        throw new Error("Image generation failed. Please try again.");
    }

    return images;
};

export const generateVideosFromPrompt = async (prompt: string, onStatusUpdate?: StatusUpdateCallback): Promise<string> => {
    console.log("Generating video for prompt:", prompt);
    
    try {
        // Veo requires creating a new instance right before call to capture API key from window selection
        const freshAi = new GoogleGenAI({ apiKey: process.env.API_KEY });
        
        if (onStatusUpdate) onStatusUpdate("Initializing video generation...");

        let operation = await freshAi.models.generateVideos({
            model: 'veo-3.1-fast-generate-preview',
            prompt: prompt,
            config: {
                numberOfVideos: 1,
                resolution: '720p',
                aspectRatio: '16:9'
            }
        });

        if (onStatusUpdate) onStatusUpdate("Video generation started (this may take a minute)...");

        // Polling loop
        while (!operation.done) {
            await new Promise(resolve => setTimeout(resolve, 10000)); // Poll every 10s
            if (onStatusUpdate) onStatusUpdate("Generating video frames...");
            operation = await freshAi.operations.getVideosOperation({operation: operation});
        }
        
        if (operation.error) {
             throw new Error(`Video generation failed: ${operation.error.message || JSON.stringify(operation.error)}`);
        }

        const videoUri = operation.response?.generatedVideos?.[0]?.video?.uri;
        if (!videoUri) throw new Error("No video URI returned");

        // The response.body contains the MP4 bytes. You must append an API key when fetching from the download link.
        const downloadUrl = `${videoUri}&key=${process.env.API_KEY}`;
        
        if (onStatusUpdate) onStatusUpdate("Downloading video...");
        const response = await fetch(downloadUrl);
        const blob = await response.blob();
        return URL.createObjectURL(blob);

    } catch (error) {
        console.error("Error generating video:", error);
        throw error;
    }
};

export const generateStoryFromPrompt = async (prompt: string, onStatusUpdate?: StatusUpdateCallback): Promise<string> => {
    console.log("Generating story for prompt:", prompt);
    const storyGenerationPrompt = `Based on the following idea, write a short, creative story. The story should be engaging and well-structured.
    
    Idea: "${prompt}"
    
    Story:`;
    try {
        const response = await withRetry<GenerateContentResponse>(() => ai.models.generateContent({
            model: 'gemini-2.5-flash',
            contents: storyGenerationPrompt,
            config: { temperature: 0.8 }
        }), 3, 1000, onStatusUpdate, "Story Generation");
        return response.text;
    } catch (error) {
        console.error("Error generating story with Gemini:", error);
        throw error;
    }
};

export const refinePromptWithGraphUpdates = async (
  originalPrompt: string,
  updates: GraphUpdate[]
): Promise<string> => {
   // ... (Keeping existing implementation)
   // Logic merged into refinePromptWithAllUpdates, but keeping this for safety if referenced elsewhere.
  console.log("Refining prompt with batched graph updates:", { originalPrompt, updates });

  const updatesList = updates.map((u, i) => {
      if (u.type === 'attribute') {
          return `${i+1}. For entity "${u.entity}", set attribute "${u.attribute}" to "${u.value}".`;
      } else {
          return `${i+1}. Change relationship between "${u.source}" and "${u.target}" from "${u.oldLabel}" to "${u.newLabel}".`;
      }
  }).join('\n');

  const prompt = `You are an expert prompt engineer. Your goal is to rewrite the prompt to seamlessly incorporate specific user edits while strictly preserving all other existing details.
  
Original Prompt: "${originalPrompt}"

List of Edits:
${updatesList}

Instructions:
1.  **Integrate Attributes:** When an attribute is set (e.g., "color" to "blue"), ensure the entity is explicitly described with that attribute in the narrative.
2.  **Update Relationships:** If a relationship changes, rewrite the interaction between the entities to reflect the new state.
3.  **Preserve Context:** CRITICAL: Do NOT remove, summarize, or condense any existing details, entities, or stylistic elements from the "Original Prompt". The goal is accretion and modification, not summarization. Only remove details if they are explicitly contradicted by the edits.
4.  **Exclusion:** CRITICAL: If an edit sets "existence" or "existence_in_image" to "false" (or "Absent"), you MUST remove that entity and its related descriptions entirely.
5.  **Style:** Maintain the original tone (e.g., if it's a story, keep it narrative; if an image prompt, keep it descriptive).

Do not add any extra explanations, just return the updated prompt string.

Updated Prompt:`;

  try {
    const response = await withRetry<GenerateContentResponse>(() => ai.models.generateContent({
      model: 'gemini-2.5-flash',
      contents: prompt,
    }));
    return response.text;
  } catch (error) {
    console.error("Error refining prompt with graph updates:", error);
    return originalPrompt;
  }
};
