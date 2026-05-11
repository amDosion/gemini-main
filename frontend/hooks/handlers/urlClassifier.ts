/**
 * URL 类型分类工具（用户友好显示标签）。
 *
 * 1:1 抽离自 `attachmentUtils.ts` L795-821
 * （< 800 行合规拆分）。
 */

/**
 * 根据 URL 协议/路径前缀 + 上传状态返回中文类别标签。
 * 用于附件预览面板等 UI 展示。
 */
export const getUrlType = (url: string | undefined, uploadStatus?: string): string => {
  if (!url) {
    return '空URL';
  }

  if (url.startsWith('data:')) {
    return 'Base64 Data URL (AI原始返回)';
  }

  if (url.startsWith('blob:')) {
    return 'Blob URL (处理后的本地URL)';
  }

  if (url.startsWith('/api/temp-images/')) {
    return '临时代理URL (后端创建)';
  }

  if (url.startsWith('/api/storage/local-files/')) {
    return '本地存储URL (已完成)';
  }

  if (url.startsWith('http://') || url.startsWith('https://')) {
    return uploadStatus === 'completed' ? '云存储URL (已上传完成)' : 'HTTP临时URL (AI原始返回)';
  }

  return '未知类型';
};
