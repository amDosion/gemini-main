
/**
 * PDF Extraction Service
 *
 * Handles PDF upload and structured data extraction with hybrid backend/local support
 */

import { PdfExtractionResult, PdfExtractionTemplate } from '../../types';

const BACKEND_URL = ''; // Use relative path to leverage Vite proxy

// Default templates for local mode (when backend is unavailable)
const DEFAULT_TEMPLATES: PdfExtractionTemplate[] = [
  {
    id: 'invoice',
    name: 'Invoice',
    description: 'Extract invoice details',
    icon: '🧾'
  },
  {
    id: 'form',
    name: 'Form',
    description: 'Extract form fields',
    icon: '📋'
  },
  {
    id: 'receipt',
    name: 'Receipt',
    description: 'Extract receipt data',
    icon: '🧾'
  },
  {
    id: 'contract',
    name: 'Contract',
    description: 'Extract contract terms',
    icon: '📄'
  }
];

export class PdfExtractionService {
  private static backendAvailable: boolean | null = null; // null = unknown, true/false = known

  /**
   * Check if backend PDF extraction is available
   */
  static async checkAvailability(force = false): Promise<boolean> {
    // Return cached result if we already checked and not forcing refresh
    if (!force && this.backendAvailable !== null) {
      return this.backendAvailable;
    }

    try {
      // Short timeout to avoid blocking UI
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 3000);

      const response = await fetch(`${BACKEND_URL}/health`, {
        method: 'GET',
        signal: controller.signal
      });
      
      clearTimeout(timeoutId);
      
      if (!response.ok) throw new Error("Health check failed");
      
      const data = await response.json();
      // Ensure backend explicitly says pdf_extraction is enabled, or fallback to true if key missing but health ok
      this.backendAvailable = data.pdf_extraction !== false; 
      return this.backendAvailable;
    } catch (error) {
      console.warn('Backend PDF extraction unavailable (using local mode):', error);
      this.backendAvailable = false;
      return false;
    }
  }

  /**
   * Get available extraction templates
   * Falls back to default templates if backend is unavailable
   */
  static async getTemplates(): Promise<PdfExtractionTemplate[]> {
    const isAvailable = await this.checkAvailability();

    if (!isAvailable) {
      return DEFAULT_TEMPLATES;
    }

    try {
      const response = await fetch(`${BACKEND_URL}/api/pdf/templates`);

      if (!response.ok) {
        throw new Error('Failed to fetch templates');
      }

      const data = await response.json();
      return data.templates || DEFAULT_TEMPLATES;
    } catch (error) {
      console.error('Error fetching templates, using defaults:', error);
      return DEFAULT_TEMPLATES;
    }
  }

  /**
   * Extract structured data from a PDF file
   * 
   * @param file - PDF file to extract
   * @param templateType - Template to use for extraction
   * @param apiKey - API key for backend extraction
   * @param additionalInstructions - Optional additional instructions
   * @param modelId - Model ID to use for extraction (required)
   * @returns Extraction result or error
   */
  static async extractFromPdf(
    file: File,
    templateType: string,
    apiKey: string,
    additionalInstructions: string = '',
    modelId: string
  ): Promise<PdfExtractionResult> {
    // Check availability again but allow retry if previously failed
    let isAvailable = await this.checkAvailability();
    
    if (!isAvailable) {
        // Try one more time forcing a check, just in case server woke up
        isAvailable = await this.checkAvailability(true);
    }

    if (!isAvailable) {
      // Backend unavailable - return error result
      return {
        success: false,
        error: 'PDF extraction backend is not available. Please start the backend server to use this feature.',
        template_type: templateType,
        template_name: templateType,
        data: {},
        raw_text: null,
        model_response: 'Backend service unavailable'
      };
    }

    // Sanitize Model ID
    // 1. Remove 'models/' prefix if present (backend might double add it or SDK mismatch)
    // 2. Map known problematic aliases to stable versions
    let safeModelId = modelId || 'gemini-1.5-flash';
    
    if (safeModelId.startsWith('models/')) {
        safeModelId = safeModelId.replace('models/', '');
    }

    // Explicitly fix the broken alias that causes backend 500s
    if (safeModelId.includes('gemini-1.5-pro-latest')) {
        safeModelId = 'gemini-1.5-pro';
    } else if (safeModelId.includes('gemini-1.5-flash-latest')) {
        safeModelId = 'gemini-1.5-flash';
    }

    // Backend available - use API
    const formData = new FormData();
    formData.append('file', file);
    formData.append('template_type', templateType);
    formData.append('api_key', apiKey);
    formData.append('additional_instructions', additionalInstructions);
    
    // Add to body
    formData.append('model_id', safeModelId);
    formData.append('model', safeModelId); // Legacy support
    formData.append('model_name', safeModelId); // Alternative

    try {
      // Robustness: Add model_id to URL as well, just in case Body parsing fails on backend
      const url = new URL(`${BACKEND_URL}/api/pdf/extract`, window.location.origin);
      url.searchParams.append('model_id', safeModelId);

      const response = await fetch(url.toString(), {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: response.statusText }));
        throw new Error(errorData.detail || `Server Error: ${response.status}`);
      }

      const result: PdfExtractionResult = await response.json();
      return result;
    } catch (error: any) {
      console.error('PDF extraction error:', error);
      return {
        success: false,
        error: error.message || 'Unknown error occurred',
        template_type: templateType,
        template_name: templateType,
        data: {},
        raw_text: null,
        model_response: null
      };
    }
  }

  /**
   * Reset backend availability check (useful for retry)
   */
  static resetAvailabilityCheck(): void {
    this.backendAvailable = null;
  }
}
