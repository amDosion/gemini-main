/**
 * PDF Extraction Service
 *
 * Handles PDF upload and structured data extraction with hybrid backend/local support
 */

import { PdfExtractionResult, PdfExtractionTemplate } from '../../types';

const BACKEND_URL = 'http://localhost:8000';

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
  static async checkAvailability(): Promise<boolean> {
    // Return cached result if we already checked
    if (this.backendAvailable !== null) {
      return this.backendAvailable;
    }

    try {
      const response = await fetch(`${BACKEND_URL}/health`, {
        method: 'GET',
        signal: AbortSignal.timeout(3000) // 3 second timeout
      });
      const data = await response.json();
      this.backendAvailable = data.pdf_extraction === true;
      return this.backendAvailable;
    } catch (error) {
      console.log('Backend PDF extraction unavailable, using local mode');
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
      console.log('Using default PDF templates (backend unavailable)');
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
   * @returns Extraction result or error
   */
  static async extractFromPdf(
    file: File,
    templateType: string,
    apiKey: string,
    additionalInstructions: string = ''
  ): Promise<PdfExtractionResult> {
    const isAvailable = await this.checkAvailability();

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

    // Backend available - use API
    const formData = new FormData();
    formData.append('file', file);
    formData.append('template_type', templateType);
    formData.append('api_key', apiKey);
    formData.append('additional_instructions', additionalInstructions);

    try {
      const response = await fetch(`${BACKEND_URL}/api/pdf/extract`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to extract PDF data');
      }

      const result: PdfExtractionResult = await response.json();
      return result;
    } catch (error) {
      console.error('PDF extraction error:', error);
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error occurred',
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
