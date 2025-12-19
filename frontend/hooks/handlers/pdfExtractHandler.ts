/**
 * PDF 提取模式处理器
 * 处理 pdf-extract 模式
 */
import { Attachment } from '../../../types';
import { PdfExtractionService } from '../../services/pdfExtractionService';
import { HandlerContext, HandlerResult } from './types';

/**
 * 处理 PDF 提取模式
 * 
 * @param text - 用户输入的额外指令
 * @param attachments - 附件列表（需包含 PDF 文件）
 * @param context - 处理器上下文
 * @returns 提取结果
 */
export const handlePdfExtract = async (
  text: string,
  attachments: Attachment[],
  context: HandlerContext
): Promise<HandlerResult> => {
  // 1. 获取 PDF 文件
  const pdfFile = attachments.find(
    att => att.file && att.mimeType === 'application/pdf'
  )?.file;

  if (!pdfFile) {
    throw new Error('No PDF file provided for extraction');
  }

  // 2. 获取模板类型
  const templateType = context.options.pdfExtractTemplate || 'invoice';

  // 3. 验证 API Key
  if (!context.apiKey) {
    throw new Error('API key is required for PDF extraction. Please configure it in Settings.');
  }

  // 4. 获取模型 ID（从 context 中获取当前选择的模型）
  const modelId = context.currentModel?.id || 'gemini-2.5-flash';

  // 5. 合并额外指令（高级设置 + 用户输入）
  const advancedInstructions = context.options.pdfAdditionalInstructions || '';
  const combinedInstructions = [advancedInstructions, text].filter(Boolean).join('\n');

  console.log('[pdfExtractHandler] 开始 PDF 提取:', {
    filename: pdfFile.name,
    size: pdfFile.size,
    templateType,
    modelId,
    additionalInstructions: combinedInstructions ? combinedInstructions.substring(0, 50) + '...' : '(none)'
  });

  // 6. 调用提取服务
  const extractionResult = await PdfExtractionService.extractFromPdf(
    pdfFile,
    templateType,
    context.apiKey,
    modelId,
    combinedInstructions // 合并后的额外指令
  );

  console.log('[pdfExtractHandler] 提取完成:', {
    success: extractionResult.success,
    error: extractionResult.error || null
  });

  // 7. 返回结果
  return {
    content: JSON.stringify(extractionResult, null, 2),
    attachments: []
  };
};
