/**
 * 图片验证工具
 * 用于验证上传的图片格式和大小
 */

export interface ImageValidationResult {
  isValid: boolean;
  error?: string;
}

/**
 * 验证图片文件
 * 
 * @param file 文件对象
 * @param maxSizeMB 最大文件大小（MB），默认 10MB
 * @param allowedFormats 允许的格式，默认 ['image/jpeg', 'image/png']
 * @returns 验证结果
 */
export function validateImageFile(
  file: File,
  maxSizeMB: number = 10,
  allowedFormats: string[] = ['image/jpeg', 'image/png']
): ImageValidationResult {
  // 验证文件格式
  if (!allowedFormats.includes(file.type)) {
    return {
      isValid: false,
      error: `不支持的文件格式。仅支持 ${allowedFormats.map(f => f.split('/')[1].toUpperCase()).join('、')}`
    };
  }
  
  // 验证文件大小
  const maxSizeBytes = maxSizeMB * 1024 * 1024;
  if (file.size > maxSizeBytes) {
    return {
      isValid: false,
      error: `文件大小超过限制。最大允许 ${maxSizeMB}MB，当前文件 ${(file.size / 1024 / 1024).toFixed(2)}MB`
    };
  }
  
  return { isValid: true };
}

/**
 * 验证 Base64 图片
 * 
 * @param base64Data Base64 编码的图片数据
 * @param maxSizeMB 最大文件大小（MB），默认 10MB
 * @returns 验证结果
 */
export function validateBase64Image(
  base64Data: string,
  maxSizeMB: number = 10
): ImageValidationResult {
  try {
    // 移除 data URL 前缀
    const base64String = base64Data.includes(',') 
      ? base64Data.split(',')[1] 
      : base64Data;
    
    // 计算文件大小（Base64 编码后大小约为原始大小的 4/3）
    const sizeBytes = (base64String.length * 3) / 4;
    const maxSizeBytes = maxSizeMB * 1024 * 1024;
    
    if (sizeBytes > maxSizeBytes) {
      return {
        isValid: false,
        error: `图片大小超过限制。最大允许 ${maxSizeMB}MB，当前图片约 ${(sizeBytes / 1024 / 1024).toFixed(2)}MB`
      };
    }
    
    // 验证格式（从 data URL 中提取）
    if (base64Data.startsWith('data:')) {
      const mimeType = base64Data.split(';')[0].split(':')[1];
      if (!['image/jpeg', 'image/png'].includes(mimeType)) {
        return {
          isValid: false,
          error: `不支持的图片格式。仅支持 JPEG、PNG`
        };
      }
    }
    
    return { isValid: true };
  } catch (error) {
    return {
      isValid: false,
      error: '图片数据格式错误'
    };
  }
}
