
import { StreamUpdate } from "../interfaces";
import { Message, Attachment, ChatOptions } from "../../../types/types";
import { resolveDashUrl } from "./api";

export async function* streamNativeDashScope(
    modelId: string,
    history: Message[],
    message: string,
    attachments: Attachment[],
    options: ChatOptions,
    apiKey: string,
    baseUrl?: string // Added baseUrl
): AsyncGenerator<StreamUpdate, void, unknown> {
    // 1. Prepare Messages
    const msgs: any[] = [];
    
    // History Processing
    for (const msg of history) {
        if (msg.isError) continue;
        if (!msg.content && (!msg.attachments || msg.attachments.length === 0)) continue; // Skip empty messages

        let role = msg.role === 'model' ? 'assistant' : msg.role;
        // Deep Research prefers 'user' over 'system' for instructions generally
        if (role === 'system') role = 'user'; 
        
        // Native Text Models usually expect text-only content structure for now
        msgs.push({
            role: role,
            content: msg.content || " " 
        });
    }
    
    // Current Message
    if (message) {
        msgs.push({ role: 'user', content: message });
    } else if (msgs.length === 0 || msgs[msgs.length - 1].role === 'assistant') {
        msgs.push({ role: 'user', content: "Continue..." });
    }

    // 2. Construct Payload
    const parameters: any = {
        result_format: 'message', 
        incremental_output: true
    };

    if (options.enableSearch) {
        parameters.enable_search = true;
        parameters.search_options = {
            enable_source: true,
            prepend_search_result: true
        };
    }

    if (options.enableThinking) {
        parameters.enable_thinking = true;
    }

    const payload = {
        model: modelId,
        input: {
            messages: msgs
        },
        parameters: parameters
    };

    // 3. Request
    const endpoint = resolveDashUrl(baseUrl || '', 'generation');
    
    try {
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${apiKey}`,
                'Content-Type': 'application/json',
                'Accept': 'text/event-stream',
                'X-DashScope-SSE': 'enable'
            },
            body: JSON.stringify(payload)
            // Removed mode: 'cors' to let browser default handle it (usually 'cors' anyway)
        });

        if (!response.ok) {
            const errText = await response.text().catch(() => response.statusText);
            let errMsg = `DashScope Error (${response.status})`;
            try {
                const jsonErr = JSON.parse(errText);
                if (jsonErr.message) errMsg += `: ${jsonErr.message}`;
                if (jsonErr.code) errMsg += ` [${jsonErr.code}]`;
            } catch (e) {
                errMsg += `: ${errText}`;
            }
            throw new Error(errMsg);
        }

        if (!response.body) throw new Error("No response body received from DashScope.");

        // 4. Stream Parsing
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';
        
        let currentPhase = '';
        let isThinking = false;

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                const trimmed = line.trim();
                if (!trimmed.startsWith('data:')) continue;
                
                const dataStr = trimmed.slice(5).trim();
                if (!dataStr) continue;

                try {
                    const json = JSON.parse(dataStr);
                    
                    if (json.code && json.message) {
                        throw new Error(`Stream Error: ${json.message}`);
                    }

                    const output = json.output;
                    if (!output) continue;

                    // --- A. Handle Search Info ---
                    if (output.search_info?.search_results) {
                        const searchResults = output.search_info.search_results;
                        if (Array.isArray(searchResults) && searchResults.length > 0) {
                             const chunks = searchResults.map((site: any) => ({
                                 web: {
                                     uri: site.url,
                                     title: site.title || "Source"
                                 }
                             }));
                             yield { text: '', groundingMetadata: { groundingChunks: chunks } };
                        }
                    }

                    // --- B. Handle Standard Response ---
                    if (output.choices && output.choices.length > 0) {
                        const msg = output.choices[0].message;
                        
                        if (msg.reasoning_content) {
                             if (!isThinking) {
                                 yield { text: '\n<thinking>\n' };
                                 isThinking = true;
                             }
                             yield { text: msg.reasoning_content };
                        }

                        if (msg.content) {
                             if (isThinking) {
                                 yield { text: '\n</thinking>\n' };
                                 isThinking = false;
                             }
                             yield { text: msg.content };
                        }
                    }

                    // --- C. Handle Deep Research Response ---
                    if (output.message) {
                        const msg = output.message;

                        if (msg.phase && msg.phase !== currentPhase) {
                             currentPhase = msg.phase;
                             if (currentPhase === 'WebResearch') {
                                 yield { text: `\n\n> 🔍 **Deep Research Status**: Started Web Research...\n\n` };
                             } else if (currentPhase === 'answer') {
                                 yield { text: `\n\n> 💡 **Formulating Answer**...\n\n` };
                             }
                        }

                        if (msg.content) {
                             yield { text: msg.content };
                        }

                        if (msg.extra?.deep_research?.research?.webSites) {
                            const sites = msg.extra.deep_research.research.webSites;
                            const chunks = sites.map((site: any) => ({
                                web: { uri: site.url, title: site.title || "Source" }
                            }));
                            yield { text: '', groundingMetadata: { groundingChunks: chunks } };
                        }
                    }

                } catch (e) {
                    // Ignore JSON parse errors on partial chunks
                }
            }
        }
        
        if (isThinking) {
             yield { text: '\n</thinking>\n' };
        }
        reader.releaseLock();

    } catch (err: any) {
        // Normalize Fetch/CORS errors
        if (err.message === 'Failed to fetch' || err.name === 'TypeError') {
            throw new Error("Network Error: Failed to fetch from DashScope. This is likely a CORS issue in the browser or an invalid URL.");
        }
        throw err;
    }
}
