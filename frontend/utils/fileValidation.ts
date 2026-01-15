import { AppMode } from '../types/types';

/**
 * 文件验证结果
 */
export interface FileValidationResult {
  valid: File[];           // 有效文件
  invalid: File[];         // 无效文件
  errors: string[];        // 错误消息
}

/**
 * 最大文件大小: 100MB
 */
const MAX_FILE_SIZE = 100 * 1024 * 1024;

/**
 * 根据模式获取接受的文件类型
 */
export function getAcceptedTypes(mode: AppMode): string[] {
  switch (mode) {
    case 'chat':
      return [
        'image/*',
        'video/*',
        'audio/*',
        'application/pdf',
        'text/*',
        'text/csv',
        'text/html',
        'application/json'
      ];
    case 'image-gen':
    case 'image-chat-edit':
    case 'image-mask-edit':
    case 'image-inpainting':
    case 'image-background-edit':
    case 'image-recontext':
    case 'image-outpainting':
    case 'video-gen':
    case 'audio-gen':
    case 'virtual-try-on':
      return ['image/*', 'video/*', 'audio/*'];
    case 'pdf-extract':
      return ['application/pdf'];
    default:
      return [];
  }
}

/**
 * 检查文件类型是否有效（支持通配符匹配）
 */
export function isValidFileType(file: File, acceptedTypes: string[]): boolean {
  if (acceptedTypes.length === 0) return true;
  
  return acceptedTypes.some(type => {
    // 通配符匹配 (如 image/*)
    if (type.endsWith('/*')) {
      const prefix = type.slice(0, -2);
      return file.type.startsWith(prefix);
    }
    // 精确匹配
    return file.type === type;
  });
}

/**
 * 检查文件大小是否有效
 */
export function isValidFileSize(file: File, maxSize: number = MAX_FILE_SIZE): boolean {
  return file.size <= maxSize;
}

/**
 * 验证文件列表
 */
export function validateFiles(
  files: File[],
  acceptedTypes: string[],
  maxSize: number = MAX_FILE_SIZE
): FileValidationResult {
  const valid: File[] = [];
  const invalid: File[] = [];
  const errors: string[] = [];

  files.forEach(file => {
    // 检查文件类型
    if (!isValidFileType(file, acceptedTypes)) {
      invalid.push(file);
      errors.push(`不支持的文件类型: ${file.name} (${file.type || '未知类型'})`);
      return;
    }

    // 检查文件大小
    if (!isValidFileSize(file, maxSize)) {
      invalid.push(file);
      const sizeMB = (file.size / (1024 * 1024)).toFixed(2);
      const maxSizeMB = (maxSize / (1024 * 1024)).toFixed(0);
      errors.push(`文件大小超过限制: ${file.name} (${sizeMB}MB > ${maxSizeMB}MB)`);
      return;
    }

    valid.push(file);
  });

  return { valid, invalid, errors };
}

/**
 * 验证文件列表（模式感知）
 */
export function validateFilesForMode(
  files: File[],
  mode: AppMode,
  currentAttachmentCount: number = 0
): FileValidationResult {
  const acceptedTypes = getAcceptedTypes(mode);
  
  // 特殊模式限制
  if (mode === 'image-outpainting') {
    // 扩图模式只允许一张图片
    if (currentAttachmentCount > 0) {
      return {
        valid: [],
        invalid: files,
        errors: ['扩图模式只支持一张图片，请先移除现有图片']
      };
    }
    
    if (files.length > 1) {
      return {
        valid: [files[0]],
        invalid: files.slice(1),
        errors: ['扩图模式只支持一张图片，已自动选择第一张']
      };
    }
  }

  return validateFiles(files, acceptedTypes);
}
