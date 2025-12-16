
import { GenerateContentResponse } from "@google/genai";
import { StreamUpdate } from "../interfaces";

export class GoogleResponseParser {
  private isThinking = false;

  public *parseChunk(chunk: GenerateContentResponse): Generator<StreamUpdate> {
    if (chunk.candidates?.[0]?.content?.parts) {
      for (const part of chunk.candidates[0].content.parts) {
        const p = part as any;
        
        // Correctly identify thought parts.
        const isThoughtPart = !!p.thought;
        
        // Handle Code Execution Results
        if (p.executableCode) {
            yield { text: `\n\`\`\`${p.executableCode.language.toLowerCase()}\n${p.executableCode.code}\n\`\`\`\n` };
        }
        if (p.codeExecutionResult) {
            yield { text: `\n> **Output:**\n> \`\`\`\n> ${p.codeExecutionResult.output}\n> \`\`\`\n` };
        }

        if (isThoughtPart) {
          if (!this.isThinking) {
            yield { text: '\n<thinking>\n' };
            this.isThinking = true;
          }
          const content = typeof p.thought === 'string' ? p.thought : p.text;
          if (content) {
             yield { text: content };
          }
        } else {
          if (this.isThinking) {
            yield { text: '\n</thinking>\n' };
            this.isThinking = false;
          }

          if (p.text) {
            yield { text: p.text };
          }

          if (p.inlineData) {
            const mimeType = p.inlineData.mimeType || 'image/png';
            const base64Data = p.inlineData.data;
            const url = `data:${mimeType};base64,${base64Data}`;
            yield {
              text: '',
              attachments: [{
                id: crypto.randomUUID(),
                mimeType: mimeType,
                name: 'Generated Image',
                url: url
              }]
            };
          }
        }
      }
    }

    if (chunk.candidates?.[0]?.groundingMetadata) {
      yield { text: '', groundingMetadata: chunk.candidates[0].groundingMetadata };
    }
    
    // @ts-ignore - Handle URL Context Metadata if present in SDK response (newer feature)
    if (chunk.candidates?.[0]?.urlContextMetadata) {
        // @ts-ignore
        yield { text: '', urlContextMetadata: chunk.candidates[0].urlContextMetadata };
    }
  }

  public *finalize(): Generator<StreamUpdate> {
      if (this.isThinking) {
          yield { text: '\n</thinking>\n' };
          this.isThinking = false;
      }
  }
}
