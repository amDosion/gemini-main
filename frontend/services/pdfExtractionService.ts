/**
 * PDF Extraction Service
 *
 * Handles PDF upload and structured data extraction with hybrid backend/local support
 * 
 * 设计原则：
 * 1. 不单独进行 health 检查，直接请求模板接口判断后端可用性
 * 2. 模板数据一次性获取并缓存，避免重复请求
 * 3. 使用 Promise 缓存防止并发重复请求
 */

import { PdfExtractionResult, PdfExtractionTemplate } from '../types/types';

// Default templates for local mode (when backend is unavailable)
const DEFAULT_TEMPLATES: PdfExtractionTemplate[] = [
  { id: 'invoice', name: 'Invoice', description: 'Extract invoice details', icon: '🧾' },
  { id: 'form', name: 'Form', description: 'Extract form fields', icon: '📋' },
  { id: 'receipt', name: 'Receipt', description: 'Extract receipt data', icon: '🧾' },
  { id: 'contract', name: 'Contract', description: 'Extract contract terms', icon: '📄' }
];

interface InitResult {
  available: boolean;
  templates: PdfExtractionTemplate[];
}

export class PdfExtractionService {
  // 统一的初始化状态
  private static initResult: InitResult | null = null;
  private static initPromise: Promise<InitResult> | null = null;

  /**
   * 初始化服务：一次请求获取后端可用性和模板数据
   * 使用 Promise 缓存防止并发重复请求
   */
  private static async initialize(): Promise<InitResult> {
    // 1. 使用已缓存的结果（优先检查）
    if (this.initResult) {
      return this.initResult;
    }

    // 2. 复用正在进行的请求（防止并发）
    if (this.initPromise) {
      return this.initPromise;
    }

    // 3. 创建新请求并立即缓存 Promise
    console.log('[PdfExtractionService] Initializing...');
    this.initPromise = (async () => {
      try {
        const result = await this.fetchTemplatesAndCheckAvailability();
        this.initResult = result;
        console.log('[PdfExtractionService] Initialized:', {
          available: result.available,
          templateCount: result.templates.length
        });
        return result;
      } catch (error) {
        // 请求失败时清除 Promise 缓存，允许重试
        this.initPromise = null;
        throw error;
      }
    })();

    return this.initPromise;
  }

  /**
   * 直接请求模板接口，成功则后端可用，失败则使用默认模板
   */
  private static async fetchTemplatesAndCheckAvailability(): Promise<InitResult> {
    try {
      const response = await fetch('/api/pdf/templates', {
        method: 'GET',
        credentials: 'include',
        signal: AbortSignal.timeout(5000)
      });

      if (!response.ok) {
        console.warn('[PdfExtractionService] Backend unavailable (status:', response.status, ')');
        return { available: false, templates: DEFAULT_TEMPLATES };
      }

      const data = await response.json();
      const templates = data.templates || DEFAULT_TEMPLATES;
      
      console.log('[PdfExtractionService] Backend available, templates:', templates.length);
      return { available: true, templates };
    } catch (error) {
      console.warn('[PdfExtractionService] Backend unavailable:', error);
      return { available: false, templates: DEFAULT_TEMPLATES };
    }
  }

  /**
   * Check if backend PDF extraction is available
   */
  static async checkAvailability(): Promise<boolean> {
    const result = await this.initialize();
    return result.available;
  }

  /**
   * Get available extraction templates
   * 一次性返回所有模板，使用缓存避免重复请求
   */
  static async getTemplates(): Promise<PdfExtractionTemplate[]> {
    const result = await this.initialize();
    return result.templates;
  }

  /**
   * Extract structured data from a PDF file
   */
  static async extractFromPdf(
    file: File,
    templateType: string,
    apiKey: string,
    modelId: string,
    additionalInstructions: string = ''
  ): Promise<PdfExtractionResult> {
    const { available } = await this.initialize();

    if (!available) {
      return {
        success: false,
        error: 'PDF extraction backend is not available. Please start the backend server.',
        template_type: templateType,
        template_name: templateType,
        data: {},
        raw_text: null,
        model_response: 'Backend service unavailable'
      };
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('template_type', templateType);
    formData.append('api_key', apiKey);
    formData.append('model_id', modelId);
    formData.append('additional_instructions', additionalInstructions);

    try {
      const response = await fetch('/api/pdf/extract', {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to extract PDF data');
      }

      return await response.json();
    } catch (error) {
      console.error('[PdfExtractionService] Extraction error:', error);
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
   * 同步获取缓存的模板（用于组件初始渲染，避免闪烁）
   * 如果缓存为空，返回默认模板
   */
  static getCachedTemplates(): PdfExtractionTemplate[] {
    return this.initResult?.templates || DEFAULT_TEMPLATES;
  }

  /**
   * 预加载模板数据（可在应用启动时调用）
   */
  static preload(): void {
    this.initialize().catch(() => {
      // 静默处理错误，使用默认模板
    });
  }

  /**
   * Reset all caches (useful for retry)
   */
  static resetAll(): void {
    this.initResult = null;
    this.initPromise = null;
    console.log('[PdfExtractionService] Cache cleared');
  }
}
