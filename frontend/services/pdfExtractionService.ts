/**
 * PDF Extraction Service
 *
 * Handles PDF upload and structured data extraction with hybrid backend/local support
 */

import { PdfExtractionResult, PdfExtractionTemplate } from '../../types';

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
  private static backendAvailable: boolean | null = null;
  private static checkPromise: Promise<boolean> | null = null;

  /**
   * Check if backend PDF extraction is available
   * Uses Promise caching to prevent concurrent duplicate requests
   */
  static async checkAvailability(): Promise<boolean> {
    // 1. 复用正在进行的请求（解决并发竞态）
    if (this.checkPromise) {
      console.log('[PdfExtractionService] Reusing ongoing check...');
      return this.checkPromise;
    }

    // 2. 使用已缓存的结果
    if (this.backendAvailable !== null) {
      console.log('[PdfExtractionService] Using cached availability:', this.backendAvailable);
      return this.backendAvailable;
    }

    // 3. 创建新请求并缓存 Promise
    console.log('[PdfExtractionService] Checking backend availability...');
    this.checkPromise = this.performHealthCheck();

    try {
      const result = await this.checkPromise;
      this.backendAvailable = result;
      return result;
    } finally {
      this.checkPromise = null;
    }
  }

  /**
   * Perform the actual health check request
   */
  private static async performHealthCheck(): Promise<boolean> {
    try {
      const response = await fetch('/health', {
        method: 'GET',
        credentials: 'include',
        signal: AbortSignal.timeout(5000)
      });

      if (!response.ok) {
        console.error('[PdfExtractionService] Health check failed with status:', response.status);
        return false;
      }

      const data = await response.json();
      console.log('[PdfExtractionService] Health check response:', data);
      const available = data.pdf_extraction === true;
      console.log('[PdfExtractionService] PDF extraction available:', available);
      return available;
    } catch (error) {
      console.error('[PdfExtractionService] Health check failed:', error);
      return false;
    }
  }

  /**
   * Get available extraction templates
   * Falls back to default templates if backend is unavailable
   * @param isAvailable - Optional: pass known availability to avoid redundant check
   */
  static async getTemplates(isAvailable?: boolean): Promise<PdfExtractionTemplate[]> {
    const available = isAvailable ?? await this.checkAvailability();

    if (!available) {
      console.log('[PdfExtractionService] Using default PDF templates (backend unavailable)');
      return DEFAULT_TEMPLATES;
    }

    try {
      const response = await fetch('/api/pdf/templates');

      if (!response.ok) {
        throw new Error('Failed to fetch templates');
      }

      const data = await response.json();
      console.log('[PdfExtractionService] Fetched templates from backend:', data.templates?.length || 0);
      return data.templates || DEFAULT_TEMPLATES;
    } catch (error) {
      console.error('[PdfExtractionService] Error fetching templates, using defaults:', error);
      return DEFAULT_TEMPLATES;
    }
  }

  /**
   * Extract structured data from a PDF file
   * 
   * @param file - PDF file to extract
   * @param templateType - Template to use for extraction
   * @param apiKey - API key for backend extraction
   * @param modelId - Model ID to use for extraction (e.g., 'gemini-2.5-flash')
   * @param additionalInstructions - Optional additional instructions
   * @returns Extraction result or error
   */
  static async extractFromPdf(
    file: File,
    templateType: string,
    apiKey: string,
    modelId: string,
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
    formData.append('model_id', modelId);
    formData.append('additional_instructions', additionalInstructions);

    try {
      // 通过 Vite 代理访问后端
      const response = await fetch('/api/pdf/extract', {
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
    this.checkPromise = null;
  }
}
