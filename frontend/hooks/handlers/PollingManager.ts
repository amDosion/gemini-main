/**
 * 轮询管理器实现
 *
 * 负责管理上传任务的状态轮询，支持并发控制和延迟启动
 * 修复问题8：追踪 delayTimerId，防止内存泄漏
 */

import { PollingConfig, PollingTask, UploadStatus, IPollingManager } from './types';

/**
 * 轮询管理器类
 * 全局单例，由 useChat Hook 创建并传递给 ExecutionContext（修复问题1）
 */
export class PollingManager implements IPollingManager {
  private tasks: Map<string, PollingTask> = new Map();
  private maxConcurrent: number = 5;
  private activeTasks: number = 0;

  /**
   * 启动轮询任务
   * @param taskId 任务 ID
   * @param config 轮询配置
   * @returns Promise，在任务完成或失败时 resolve
   */
  startPolling(taskId: string, config: PollingConfig): Promise<void> {
    return new Promise((resolve, reject) => {
      // 同 id 重复启动时先停掉旧生命周期:否则旧任务的 in-flight 轮询在身份校验失败后
      // 直接 return,已占用的并发额度永远不归还,最终冻结所有新任务。
      // (旧 Promise 与既有 stopPolling 语义一致地保持未决,由 GC 回收。)
      if (this.tasks.has(taskId)) {
        this.stopPolling(taskId);
      }

      const task: PollingTask = {
        taskId,
        config,
        attempts: 0,
        startTime: Date.now(),
      };

      this.tasks.set(taskId, task);

      // 如果达到并发上限，等待；每次唤醒后重新检查并发额度，避免单次延迟后无条件启动
      const waitForSlot = () => {
        // 追踪延迟定时器（修复问题8）
        task.delayTimerId = window.setTimeout(() => {
          task.delayTimerId = undefined;
          if (this.activeTasks >= this.maxConcurrent) {
            waitForSlot();
          } else {
            this.pollOnce(task, resolve, reject);
          }
        }, config.interval);
      };

      if (this.activeTasks >= this.maxConcurrent) {
        waitForSlot();
      } else {
        this.pollOnce(task, resolve, reject);
      }
    });
  }

  /**
   * 执行一次轮询
   */
  private async pollOnce(
    task: PollingTask,
    resolve: () => void,
    reject: (error: Error) => void
  ): Promise<void> {
    // 并发额度按任务生命周期只占用一次（首次轮询时），而非每次重试都累加
    if (task.attempts === 0) {
      this.activeTasks++;
    }
    task.attempts++;

    try {
      const status = await task.config.onStatusCheck(task.taskId);

      // 状态检查进行中任务可能已被 stopPolling/cleanup 取消，此时不再回调或续期
      if (this.tasks.get(task.taskId) !== task) {
        return;
      }

      if (status.status === 'completed') {
        task.config.onSuccess?.(task.taskId, status.result);
        this.cleanupTask(task.taskId);
        this.activeTasks--;
        resolve();
        return;
      }

      if (status.status === 'failed') {
        const error = new Error(status.error || status.errorMessage || 'Upload failed');
        this.failTask(task, error, reject);
        return;
      }

      // 检查是否超时
      if (task.config.timeout && Date.now() - task.startTime > task.config.timeout) {
        this.failTask(task, new Error('Polling timeout'), reject);
        return;
      }

      // 检查是否达到最大尝试次数
      if (task.attempts >= task.config.maxAttempts) {
        this.failTask(task, new Error('Max polling attempts reached'), reject);
        return;
      }

      // 继续轮询
      task.timerId = window.setTimeout(() => {
        this.pollOnce(task, resolve, reject);
      }, task.config.interval);
    } catch (error) {
      // 同样防止已取消任务在异常路径上重复扣减额度或触发失败回调
      if (this.tasks.get(task.taskId) !== task) {
        return;
      }
      this.failTask(task, error as Error, reject);
    }
  }

  /**
   * 以失败终止任务：通知回调、清理并 reject
   */
  private failTask(task: PollingTask, error: Error, reject: (error: Error) => void): void {
    task.config.onFailure?.(task.taskId, error);
    this.cleanupTask(task.taskId);
    this.activeTasks--;
    reject(error);
  }

  /**
   * 停止轮询任务
   * 修复问题8：清理 timerId 和 delayTimerId，防止内存泄漏
   * @param taskId 任务 ID
   */
  stopPolling(taskId: string): void {
    const task = this.tasks.get(taskId);
    if (task) {
      // 清理轮询定时器
      if (task.timerId) {
        clearTimeout(task.timerId);
      }
      // 清理延迟定时器（修复问题8）
      if (task.delayTimerId) {
        clearTimeout(task.delayTimerId);
      }
      // 已启动的任务（含状态检查进行中）归还并发额度；仅在排队等待的任务从未占用额度
      if (task.attempts > 0) {
        this.activeTasks--;
      }
    }
    this.cleanupTask(taskId);
  }

  /**
   * 清理所有轮询任务
   */
  cleanup(): void {
    this.tasks.forEach((task) => {
      if (task.timerId) {
        clearTimeout(task.timerId);
      }
      // 清理延迟定时器（修复问题8）
      if (task.delayTimerId) {
        clearTimeout(task.delayTimerId);
      }
    });
    this.tasks.clear();
    this.activeTasks = 0;
  }

  /**
   * 清理单个任务
   */
  private cleanupTask(taskId: string): void {
    this.tasks.delete(taskId);
  }
}
