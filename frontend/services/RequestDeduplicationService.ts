/**
 * @class RequestDeduplicationService
 * @description 用于处理重复请求的服务，确保对于同一个查询在同一时间内只有一个正在进行的请求。
 */
class RequestDeduplicationService {
  private pendingRequests: Map<string, Promise<any>> = new Map();

  /**
   * 检查是否存在正在进行的请求。
   * @param {string} key - 请求的唯一标识符。
   * @returns {boolean} 如果存在正在进行的请求，则返回 true，否则返回 false。
   */
  public hasPendingRequest(key: string): boolean {
    return this.pendingRequests.has(key);
  }

  /**
   * 获取一个正在进行的请求。
   * @template T
   * @param {string} key - 请求的唯一标识符。
   * @returns {Promise<T> | null} 如果存在正在进行的请求，则返回对应的 Promise，否则返回 null。
   */
  public getPendingRequest<T>(key: string): Promise<T> | null {
    const pending = this.pendingRequests.get(key);
    return pending ? (pending as Promise<T>) : null;
  }

  /**
   * 添加一个新的正在进行的请求。
   * 当请求完成（无论成功或失败）时，会自动从列表中移除。
   * @template T
   * @param {string} key - 请求的唯一标识符。
   * @param {Promise<T>} promise - 代表正在进行的请求的 Promise。
   */
  public addPendingRequest<T>(key: string, promise: Promise<T>): void {
    this.pendingRequests.set(key, promise);

    promise.finally(() => {
      this.removePendingRequest(key);
    });
  }

  /**
   * 移除一个已完成的请求。
   * @param {string} key - 请求的唯一标识符。
   */
  public removePendingRequest(key: string): void {
    this.pendingRequests.delete(key);
  }
}

export const requestDeduplicationService = new RequestDeduplicationService();
