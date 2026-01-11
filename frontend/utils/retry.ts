import { handleError, ErrorHandlerResult } from './errorHandler';

// 定义重试配置选项的接口
export interface RetryOptions {
  maxRetries?: number; // 最大重试次数，默认为 3
  initialDelay?: number; // 初始延迟时间（毫秒），默认为 1000ms
  maxDelay?: number; // 最大延迟时间（毫秒），默认为 32000ms
  backoffMultiplier?: number; // 退避倍数，默认为 2
}

// 定义可重试的错误代码集合
const RETRYABLE_CODES = new Set([
  'RESOURCE_EXHAUSTED', // 资源耗尽（如速率限制）
  'SERVICE_UNAVAILABLE', // 服务不可用
  'TIMEOUT', // 请求超时
  'NETWORK_ERROR', // 网络错误
]);

/**
 * 异步延迟函数，用于在重试之间等待。
 * @param ms - 延迟的毫秒数
 * @returns {Promise<void>} - 在指定时间后解析的 Promise
 */
function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * 使用指数退避策略重试异步函数。
 * @template T - 异步函数的返回类型
 * @param fn - 要重试的异步函数
 * @param options - 重试配置选项
 * @returns {Promise<T>} - 成功时返回函数结果，失败时抛出最后一次错误
 */
export async function retryWithBackoff<T>(
  fn: () => Promise<T>,
  options: RetryOptions = {}
): Promise<T> {
  // 设置默认值
  const {
    maxRetries = 3,
    initialDelay = 1000,
    maxDelay = 32000,
    backoffMultiplier = 2,
  } = options;

  let lastError: any;

  // 尝试执行函数，最多 maxRetries + 1 次（初始尝试 + 重试次数）
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      // 尝试执行函数
      const result = await fn();
      return result; // 成功则立即返回结果
    } catch (error) {
      lastError = error;

      // 使用 errorHandler 分类错误
      const errorResult: ErrorHandlerResult = handleError(error);

      // 检查错误是否可重试
      const isRetryable = RETRYABLE_CODES.has(errorResult.code);

      // 如果不可重试，或者已经是最后一次尝试，则直接抛出错误
      if (!isRetryable || attempt === maxRetries) {
        throw error;
      }

      // 计算下一次重试的延迟时间（指数退避）
      // 公式: min(initialDelay * (backoffMultiplier ^ attempt), maxDelay)
      const delay = Math.min(
        initialDelay * Math.pow(backoffMultiplier, attempt),
        maxDelay
      );

      // 等待延迟时间后再进行下一次重试
      await sleep(delay);
    }
  }

  // 如果所有重试都失败，抛出最后一次捕获的错误
  throw lastError;
}
