/**
 * PDF 提取模式处理器
 * 处理 pdf-extract 模式
 */
import { Attachment } from '../../../types';
import { PdfExtractionService } from '../../services/pdfExtractionService';
import { HandlerContext, HandlerResult } from './types';

/**
 * 处理 PDF 提取模式
 */
export const handlePdfExtract = async (
  text: string,
  attachments: Attachment[],
  context: HandlerContext
): Promise<HandlerResult> => {
  // 获取 PDF 文件
  const pdfFile = attachments.find(att => att.file && att.mimeType === 'application/pdf')?.file;

  if (!pdfFile) {
    throw new Error('No PDF file provided for extraction');
  }

  const templateType = context.options.pdfExtractTemplate || 'invoice';

  // 验证 API Key
  if (!context.apiKey) {
    throw new Error('API key is required for PDF extraction. Please configure it in Settings.');
  }

  // 验证模型
  if (!context.currentModel || !context.currentModel.id) {
    throw new Error('Model is required for PDF extraction. Please select a model.');
  }

  // 使用 baseModelId（如果有）或 id
  const modelIdToUse = context.currentModel.baseModelId || context.currentModel.id;
  
  console.log('[pdfExtractHandler] Using model:', modelIdToUse);

  const extractionResult = await PdfExtractionService.extractFromPdf(
    pdfFile,
    templateType,
    context.apiKey,
    text, // 使用提示文本作为额外指令
    modelIdToUse
  );

  return {
    content: JSON.stringify(extractionResult, null, 2),
    attachments: []
  };
};
