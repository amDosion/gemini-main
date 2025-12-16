
import { GoogleGenAI } from "@google/genai";

/**
 * Parses the user-provided Base URL and API Key to construct SDK options.
 * Handles the logic for v1 vs v1beta stripping for proxy compatibility.
 */
export function getSdkOptions(apiKey: string, baseUrl: string) {
    const options: any = { apiKey: apiKey || process.env.API_KEY };
    let apiVersion = 'v1beta'; // Default

    // If Custom URL is provided
    if (baseUrl && baseUrl.trim()) {
        let cleanUrl = baseUrl.trim().replace(/\/$/, '');
        
        // The GoogleGenAI SDK automatically appends '/v1beta' or '/v1'.
        // We strip these suffixes if the user included them to prevent duplication.
        // We also detect the user's intent (stable v1 vs beta) based on the suffix.
        if (cleanUrl.endsWith('/v1beta')) {
             apiVersion = 'v1beta';
             cleanUrl = cleanUrl.substring(0, cleanUrl.length - '/v1beta'.length);
        } else if (cleanUrl.endsWith('/v1')) {
             apiVersion = 'v1';
             cleanUrl = cleanUrl.substring(0, cleanUrl.length - '/v1'.length);
        }
        
        // Remove trailing slash again
        cleanUrl = cleanUrl.replace(/\/$/, '');

        // If the URL is not empty after stripping, use it
        if (cleanUrl) {
            options.baseUrl = cleanUrl;
        }
    }
    
    options.apiVersion = apiVersion;
    return options;
}

/**
 * Creates a configured GoogleGenAI client instance.
 */
export function createGoogleClient(apiKey: string, baseUrl: string): GoogleGenAI {
    const options = getSdkOptions(apiKey, baseUrl);
    return new GoogleGenAI(options);
}
