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
      const task: PollingTask = {
        taskId,
        config,
        attempts: 0,
        startTime: Date.now()
      };
      
      this.tasks.set(taskId, task);
      
      // 如果达到并发上限，等待
      if (this.activeTasks >= this.maxConcurrent) {
        // 追踪延迟定时器（修复问题8）
        task.delayTimerId = window.setTimeout(() => {
          task.delayTimerId = undefined;
          this.pollOnce(task, resolve, reject);
        }, config.interval);
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
    this.activeTasks++;
    task.attempts++;
    
    try {
      const status = await task.config.onStatusCheck(task.taskId);
      
      if (status.status === 'completed') {
        task.config.onSuccess?.(task.taskId, status.result);
        this.cleanupTask(task.taskId);
        this.activeTasks--;
        resolve();
        return;
      }
      
      if (status.status === 'failed') {
        const error = new Error(status.error || status.errorMessage || 'Upload failed');
        task.config.onFailure?.(task.taskId, error);
        this.cleanupTask(task.taskId);
        this.activeTasks--;
        reject(error);
        return;
      }
      
      // 检查是否超时
      if (task.config.timeout && Date.now() - task.startTime > task.config.timeout) {
        const error = new Error('Polling timeout');
        task.config.onFailure?.(task.taskId, error);
        this.cleanupTask(task.taskId);
        this.activeTasks--;
        reject(error);
        return;
      }
      
      // 检查是否达到最大尝试次数
      if (task.attempts >= task.config.maxAttempts) {
        const error = new Error('Max polling attempts reached');
        task.config.onFailure?.(task.taskId, error);
        this.cleanupTask(task.taskId);
        this.activeTasks--;
        reject(error);
        return;
      }
      
      // 继续轮询
      task.timerId = window.setTimeout(() => {
        this.pollOnce(task, resolve, reject);
      }, task.config.interval);
      
    } catch (error) {
      task.config.onFailure?.(task.taskId, error as Error);
      this.cleanupTask(task.taskId);
      this.activeTasks--;
      reject(error as Error);
    }
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
        this.activeTasks--;
      }
      // 清理延迟定时器（修复问题8）
      if (task.delayTimerId) {
        clearTimeout(task.delayTimerId);
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
