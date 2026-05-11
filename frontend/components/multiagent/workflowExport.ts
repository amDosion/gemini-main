/**
 * Multi-agent workflow PNG/SVG 导出辅助工具集。
 *
 * 1:1 抽离自 `MultiAgentWorkflowEditorReactFlow.tsx` L91-221
 * （JIRA-frontend-view-decomposition.md P1 #3 Step 1）。
 *
 * 处理：
 * - 导出尺寸常量（最小宽高 / PNG 最大边长 / 像素上限）
 * - 临时图 URL 重写（避免导出时被重定向）
 * - 工作流节点类型分类（哪些是"输入节点"不计入"结果输出"）
 * - 错误格式化（多种错误类型 → 用户可读消息）
 * - 等待 DOM <img> 加载完成（用于 html-to-image 等克隆场景）
 */

/** 后端临时图 URL 路径前缀（导出时需附加 no_redirect/export=1 参数） */
export const TEMP_IMAGE_PATH_SEGMENT = '/api/temp-images/';

/** 导出画布外边距（像素） */
export const EXPORT_NODE_PADDING = 280;

/** 导出 PNG 最小宽度 */
export const EXPORT_MIN_WIDTH = 1920;

/** 导出 PNG 最小高度 */
export const EXPORT_MIN_HEIGHT = 1080;

/** 导出 PNG 单边最大像素（浏览器/Canvas 上限考虑） */
export const EXPORT_PNG_MAX_SIDE = 8192;

/** 导出 PNG 总像素上限 */
export const EXPORT_PNG_MAX_PIXELS = 85_000_000;

/** 导出 PNG 目标像素（用于动态计算 devicePixelRatio） */
export const EXPORT_PNG_TARGET_PIXELS = 140_000_000;

/** 不计入"结果输出"的节点类型（输入类节点） */
export const NON_RESULT_WORKFLOW_NODE_TYPES = new Set([
  'start',
  'input_text',
  'input_image',
  'input_video',
  'input_audio',
  'input_file',
]);

/**
 * 将 number 限制在 [min, max] 范围内。
 * 非有限数返回 min（保守 fallback）。
 */
export const clampNumber = (value: number, min: number, max: number): number => {
  if (!Number.isFinite(value)) return min;
  return Math.max(min, Math.min(max, value));
};

/**
 * 将导出过程中抛出的各种错误格式化为用户可读的中文消息。
 * 支持 Error / Event / string / object（有 message 字段或可 JSON 序列化）。
 */
export const formatWorkflowExportError = (error: unknown): string => {
  if (error instanceof Error && typeof error.message === 'string' && error.message.trim()) {
    return error.message.trim();
  }
  if (error instanceof Event) {
    return error.type ? `浏览器事件: ${error.type}` : '浏览器事件';
  }
  if (typeof error === 'string') {
    return error.trim() || '未知错误';
  }
  if (error && typeof error === 'object') {
    const maybeMessage = (error as { message?: unknown }).message;
    if (typeof maybeMessage === 'string' && maybeMessage.trim()) {
      return maybeMessage.trim();
    }
    try {
      const serialized = JSON.stringify(error);
      if (serialized && serialized !== '{}') {
        return serialized;
      }
    } catch {
      // ignore JSON stringify errors
    }
  }
  return String(error || '未知错误');
};

/**
 * 给后端临时图 URL 附加 `no_redirect=1&export=1` 参数，
 * 避免被后端重定向到原始 URL（导出时需要本地资源直接访问）。
 */
export const ensureTempImageNoRedirect = (rawUrl: string): string => {
  const value = String(rawUrl || '').trim();
  if (!value) return value;
  try {
    const parsed = new URL(value, window.location.origin);
    if (!parsed.pathname.startsWith(TEMP_IMAGE_PATH_SEGMENT)) {
      return value;
    }
    parsed.searchParams.set('no_redirect', '1');
    parsed.searchParams.set('export', '1');
    return `${parsed.pathname}?${parsed.searchParams.toString()}`;
  } catch {
    return value;
  }
};

/**
 * 判断节点是否是"非结果输出"（输入节点 / start 节点等）。
 * 用于导出时筛选"产生结果"的节点。
 */
export const isNonResultWorkflowOutputNode = (nodeId: string, nodeType: string): boolean => {
  const normalizedNodeType = String(nodeType || '')
    .trim()
    .toLowerCase();
  if (NON_RESULT_WORKFLOW_NODE_TYPES.has(normalizedNodeType)) {
    return true;
  }
  const normalizedNodeId = String(nodeId || '')
    .trim()
    .toLowerCase();
  return (
    normalizedNodeId.startsWith('start') ||
    normalizedNodeId.startsWith('input-') ||
    normalizedNodeId.startsWith('input_')
  );
};

/**
 * 等待容器内所有 <img> 加载完成（用于 html-to-image 克隆场景）。
 * 已 complete 的图片立即 resolve；其余监听 load/error；超过 timeoutMs 强制 resolve。
 */
export const waitForClonedImages = async (
  container: HTMLElement,
  timeoutMs = 10000
): Promise<void> => {
  const images = Array.from(container.querySelectorAll('img[src]')) as HTMLImageElement[];
  if (images.length === 0) {
    return;
  }

  await Promise.all(
    images.map(
      (img) =>
        new Promise<void>((resolve) => {
          if (img.complete) {
            resolve();
            return;
          }

          const cleanup = () => {
            window.clearTimeout(timer);
            img.removeEventListener('load', onComplete);
            img.removeEventListener('error', onComplete);
          };
          const onComplete = () => {
            cleanup();
            resolve();
          };
          const timer = window.setTimeout(onComplete, timeoutMs);
          img.addEventListener('load', onComplete);
          img.addEventListener('error', onComplete);
        })
    )
  );
};
