/**
 * 策略注册表实现
 * 
 * 负责管理和选择 Handler，使用 Map 数据结构提供 O(1) 查找性能
 */

import { ModeHandler, HandlerErrorImpl, HandlerMode } from './types';

/**
 * 策略注册表类
 * 单例模式，全局只有一个实例
 */
export class StrategyRegistry {
  private strategies: Map<HandlerMode, ModeHandler>;
  private finalized: boolean = false;
  
  constructor() {
    this.strategies = new Map();
  }
  
  /**
   * 注册一个 Handler
   * @param mode 应用模式
   * @param handler Handler 实例
   * @throws Error 如果注册表已经被锁定
   */
  register(mode: HandlerMode, handler: ModeHandler): void {
    if (this.finalized) {
      throw new Error('Cannot register handler after registry is finalized');
    }
    this.strategies.set(mode, handler);
  }
  
  /**
   * 锁定注册表，防止运行时动态注册
   * 应该在模块加载完成后调用
   */
  finalize(): void {
    this.finalized = true;
  }
  
  /**
   * 获取指定模式的 Handler
   * @param mode 应用模式
   * @returns Handler 实例
   * @throws HandlerError 如果找不到对应的 Handler（统一错误类型，修复问题4）
   */
  getHandler(mode: HandlerMode): ModeHandler {
    const handler = this.strategies.get(mode);
    if (!handler) {
      throw new HandlerErrorImpl(
        `No handler registered for mode: ${mode}`,
        'HANDLER_NOT_FOUND',
        'INVALID_ARGUMENT',
        { mode, sessionId: '' }
      );
    }
    return handler;
  }
  
  /**
   * 检查是否注册了指定模式的 Handler
   * @param mode 应用模式
   * @returns 是否已注册
   */
  hasHandler(mode: HandlerMode): boolean {
    return this.strategies.has(mode);
  }
}
