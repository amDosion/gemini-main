
import { createGoogleClient } from "./utils";

export class GoogleFileService {
  /**
   * Uploads a file to Google AI Studio via the Files API.
   * Handles the upload process and polls for the file to become ACTIVE.
   */
  public async uploadFile(file: File, apiKey: string, baseUrl: string): Promise<string> {
    const ai = createGoogleClient(apiKey, baseUrl);
    
    console.log(`[GoogleFileService] Uploading ${file.name} (${file.type})...`);

    try {
        const response = await ai.files.upload({
          file: file,
          config: { displayName: file.name, mimeType: file.type }
        });
        
        // @ts-ignore - SDK typing might vary between versions, handling both structure
        const fileData = response.file || response;
        const uri = fileData.uri;
        const name = fileData.name; // 'files/...'

        if (!uri) throw new Error("Failed to get file URI from Google API.");

        // Check state. If PROCESSING, poll until ACTIVE or FAILED.
        // Images are usually instant, but PDFs and Videos take time.
        if (fileData.state === 'PROCESSING') {
            console.log(`[GoogleFileService] File ${name} is processing. Polling...`);
            let state = fileData.state;
            let attempts = 0;
            const maxAttempts = 60; // 2 minutes approx

            while (state === 'PROCESSING' && attempts < maxAttempts) {
                await new Promise(resolve => setTimeout(resolve, 2000));
                const check = await ai.files.get({ name: name });
                // @ts-ignore
                state = check.file?.state || check.state;
                attempts++;
                
                if (state === 'FAILED') {
                    throw new Error("File processing failed on Google servers.");
                }
            }

            if (state !== 'ACTIVE') {
                console.warn(`[GoogleFileService] File ${name} is not ACTIVE after polling (State: ${state}). Usage might fail.`);
            } else {
                console.log(`[GoogleFileService] File ${name} is now ACTIVE.`);
            }
        }

        return uri;
    } catch (error: any) {
        console.error("[GoogleFileService] Upload failed", error);
        throw new Error(`Failed to upload file: ${error.message || 'Unknown error'}`);
    }
  }
}

export const googleFileService = new GoogleFileService();
