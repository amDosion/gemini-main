# Implementation Plan

- [ ] 1. 创建核心接口和类型定义
  - [ ] 1.1 创建 `ModeHandler` 接口
    - 定义 `execute` 方法签名
    - 定义可选的生命周期钩子（onStart、onComplete、onError、onCancel）
    - 添加完整的 TypeScript 类型注解和 JSDoc 注释
    - _Requirements: 3.1, 5.2, 5.4_
  
  - [ ] 1.2 创建 `ExecutionContext` 接口
    - 定义所有必需的上下文字段（sessionId、messageId、mode 等）
    - 定义回调函数类型（onStreamUpdate、onProgressUpdate）
    - 定义服务实例引用
    - **新增**：添加 `pollingManager` 字段（全局单例，由 useChat Hook 创建并传递）
    - _Requirements: 3.3, 5.4_
    - _Fixes: 问题 1（pollingManager 作用域）_
  
  - [ ] 1.3 创建 `HandlerResult` 接口
    - 定义标准返回字段（content、attachments）
    - 定义可选的元数据字段（groundingMetadata、urlContextMetadata 等）
    - 定义上传任务相关字段（uploadTask、dbAttachments）
    - _Requirements: 3.4, 5.4_
  
  - [ ] 1.4 创建 `Preprocessor` 接口
    - 定义 `canHandle` 方法
    - 定义 `process` 方法
    - **新增**：添加 `priority` 字段（可选，数字越小优先级越高）
    - _Fixes: 问题 2（PreprocessorRegistry 执行顺序）_
  
  - [ ] 1.5 创建 `PollingTask` 接口
    - 定义 `taskId`、`config`、`attempts`、`timerId`、`startTime` 字段
    - **新增**：添加 `delayTimerId` 字段（延迟启动的定时器 ID）
    - _Fixes: 问题 8（PollingManager 延迟定时器追踪）_

- [ ] 2. 实现策略注册表
  - [ ] 2.1 实现 `StrategyRegistry` 类
    - 使用 Map 数据结构存储策略映射
    - 实现 `register(mode, handler)` 方法
    - 实现 `getHandler(mode)` 方法，找不到时抛出 `HandlerError`（统一错误类型）
    - 实现 `hasHandler(mode)` 方法
    - 实现 `finalize()` 方法，锁定注册表防止运行时动态注册
    - _Requirements: 1.4, 1.5, 2.2_
    - _Fixes: 问题 4（错误类型统一）_
  
  - [ ]* 2.2 编写 `StrategyRegistry` 的属性测试
    - **Property 1: 策略注册完整性**
    - **Validates: Requirements 1.4**
    - 生成所有 AppMode 枚举值，验证每个都有对应的 Handler
  
  - [ ]* 2.3 编写 `StrategyRegistry` 的单元测试
    - 测试 register() 方法
    - 测试 getHandler() 方法的正常和异常情况
    - 测试 hasHandler() 方法
    - _Requirements: 1.4, 1.5_

- [ ] 3. 实现抽象基类和工具函数
  - [ ] 3.1 实现 `BaseHandler` 抽象类
    - 使用模板方法模式实现 `execute` 方法（final，不允许子类覆盖）
    - 定义抽象方法 `doExecute`，由子类实现
    - 自动调用 `validateContext` 和 `validateAttachments`
    - 实现 `handleUploadWithPolling` 方法（使用全局 pollingManager）
    - 实现 `submitUploadTasks` 方法
    - 实现 `startUploadPolling` 方法（使用 context.pollingManager）
    - 实现 `handleError` 方法进行错误标准化
    - _Requirements: 6.1, 6.2, 6.3, 6.5_
    - _Fixes: 问题 5（模板方法模式）、问题 1（全局 pollingManager）、问题 7（Promise rejection 捕获）_
  
  - [ ] 3.2 创建上传工具模块 `uploadUtils.ts`
    - 提取上传任务提交逻辑
    - 提供可复用的上传函数
    - _Requirements: 6.2_
  
  - [ ] 3.3 创建轮询工具模块 `pollingUtils.ts`
    - 提取轮询状态检查逻辑
    - 提取日志输出逻辑
    - 提供可配置的轮询参数（间隔、最大次数）
    - _Requirements: 6.3_
  
  - [ ] 3.4 实现 `PollingManager` 类
    - 实现 `startPolling` 方法，追踪 `delayTimerId`
    - 实现 `stopPolling` 方法，清理 `timerId` 和 `delayTimerId`
    - 实现 `pollOnce` 方法
    - 实现 `cleanup` 方法
    - _Fixes: 问题 8（PollingManager 延迟定时器追踪）_
  
  - [ ] 3.5 实现 `PreprocessorRegistry` 类
    - 实现 `register` 方法，按优先级排序
    - 实现 `process` 方法，按优先级顺序执行
    - 错误传播策略：任何 preprocessor 失败都会中断整个链路
    - _Fixes: 问题 2（PreprocessorRegistry 执行顺序）_
  
  - [ ] 3.6 实现 `GoogleFileUploadPreprocessor` 类
    - 设置 `priority = 10`（高优先级）
    - 实现 `canHandle` 方法
    - 实现 `process` 方法，使用深拷贝确保不可变性
    - 实现 `uploadFiles` 方法，使用 `Promise.allSettled` 并行上传
    - 实现 `deepClone` 方法
    - 支持部分失败处理
    - _Fixes: 问题 3（ExecutionContext 不可变性）、问题 6（部分失败处理）_
  
  - [ ] 3.7 创建错误处理工具模块 `errorUtils.ts`
    - 实现错误对象标准化函数
    - 实现错误类型判断函数（isQuotaError、isBadRequest 等）
    - 实现错误消息格式化函数
    - _Requirements: 6.5, 3.5_

- [ ] 4. 实现具体的 Handler 类
  - [ ] 4.1 实现 `ChatHandler`
    - 继承 `BaseHandler`
    - 实现 `doExecute` 方法（不是 `execute`），调用现有的 `handleChat` 函数
    - 实现 `buildHandlerContext` 辅助方法
    - 处理流式更新回调
    - _Requirements: 1.2, 1.3, 3.2_
    - _Fixes: 问题 5（模板方法模式）_
  
  - [ ] 4.2 实现 `ImageGenHandler`
    - 继承 `BaseHandler`
    - 实现 `doExecute` 方法（不是 `execute`），调用现有的 `handleImageGen` 函数
    - 实现 `wrapUploadTask` 方法处理上传任务
    - 使用 BaseHandler 的轮询功能
    - _Requirements: 1.2, 1.3, 3.2_
    - _Fixes: 问题 5（模板方法模式）_
  
  - [ ] 4.3 实现 `ImageEditHandler`
    - 继承 `BaseHandler`
    - 实现 `doExecute` 方法（不是 `execute`），调用现有的 `handleImageEdit` 函数
    - 处理用户附件和结果附件的上传
    - 使用 BaseHandler 的轮询功能
    - _Requirements: 1.2, 1.3, 3.2_
    - _Fixes: 问题 5（模板方法模式）_
  
  - [ ] 4.4 实现 `ImageOutpaintingHandler`
    - 继承 `BaseHandler`
    - 实现 `doExecute` 方法（不是 `execute`），调用现有的 `handleImageExpand` 函数
    - 处理图片扩展的上传任务
    - _Requirements: 1.2, 1.3, 3.2_
    - _Fixes: 问题 5（模板方法模式）_
  
  - [ ] 4.5 实现 `VirtualTryOnHandler`
    - 继承 `BaseHandler`
    - 实现 `doExecute` 方法（不是 `execute`），调用现有的 `handleVirtualTryOn` 函数
    - 处理虚拟试穿的上传任务
    - _Requirements: 1.2, 1.3, 3.2_
    - _Fixes: 问题 5（模板方法模式）_
  
  - [ ] 4.6 实现 `VideoGenHandler`
    - 继承 `BaseHandler`
    - 实现 `doExecute` 方法（不是 `execute`），调用现有的 `handleVideoGen` 函数
    - 处理视频生成的附件
    - _Requirements: 1.2, 1.3, 3.2_
    - _Fixes: 问题 5（模板方法模式）_
  
  - [ ] 4.7 实现 `AudioGenHandler`
    - 继承 `BaseHandler`
    - 实现 `doExecute` 方法（不是 `execute`），调用现有的 `handleAudioGen` 函数
    - 处理音频生成的附件
    - _Requirements: 1.2, 1.3, 3.2_
    - _Fixes: 问题 5（模板方法模式）_
  
  - [ ] 4.8 实现 `PdfExtractHandler`
    - 继承 `BaseHandler`
    - 实现 `doExecute` 方法（不是 `execute`），调用现有的 `handlePdfExtract` 函数
    - 处理 PDF 提取的结果
    - _Requirements: 1.2, 1.3, 3.2_
    - _Fixes: 问题 5（模板方法模式）_
  
  - [ ]* 3.8 编写工具函数的单元测试
    - 测试上传工具函数
    - 测试轮询工具函数
    - 测试错误处理工具函数
    - 测试 PollingManager 的延迟定时器追踪
    - 测试 PreprocessorRegistry 的优先级排序
    - 测试 GoogleFileUploadPreprocessor 的深拷贝和部分失败处理
    - _Requirements: 6.2, 6.3, 6.5_
    - **Property 5: 接口一致性** - 验证所有 Handler 实现 ModeHandler 接口
    - **Property 8: Handler 职责单一性** - 验证每个 Handler 只处理一种模式
    - **Property 10: 返回值标准化** - 验证返回值符合 HandlerResult 接口
    - **Validates: Requirements 2.3, 3.2, 3.4**
  
  - [ ]* 4.10 编写 Handler 的单元测试
    - 为每个 Handler 编写单元测试
    - 测试 execute() 方法的正常流程
    - 测试错误处理
    - _Requirements: 1.2, 1.3, 3.2_

- [ ] 5. 创建 Handler 注册配置
  - [ ] 5.1 创建 `strategyConfig.ts` 配置文件
    - 创建全局 StrategyRegistry 实例
    - 注册所有 Handler 到对应的 AppMode
    - 导出配置好的 registry 实例
    - 添加清晰的注释说明注册流程
    - _Requirements: 1.4, 5.1, 5.3_
  
  - [ ]* 5.2 编写配置完整性测试
    - **Property 1: 策略注册完整性** - 验证所有 AppMode 都已注册
    - **Validates: Requirements 1.4**

- [ ] 6. 重构 useChat Hook
  - [ ] 6.1 重构 `sendMessage` 函数 - 移除 if-else 链
    - 保留前置逻辑（初始化、文件上传、创建消息）
    - **新增**：创建全局 `pollingManager` 实例（使用 `useMemo`）
    - **新增**：将 `pollingManager` 添加到 `ExecutionContext`
    - **新增**：使用 `PreprocessorRegistry` 处理文件上传（替代原有逻辑）
    - 替换巨大的 if-else 链为策略调用
    - 使用 `registry.getHandler(mode)` 获取 Handler
    - 调用 `handler.execute(context)` 执行业务逻辑
    - 保留后置逻辑（结果处理、错误处理、状态管理）
    - **新增**：在错误恢复时调用 `context.pollingManager.cleanup()`
    - _Requirements: 1.1, 1.2, 2.1, 2.4, 2.5_
    - _Fixes: 问题 1（pollingManager 作用域）_
  
  - [ ] 6.2 实现生命周期钩子调用
    - 在 execute 前调用 onStart（如果定义）
    - 在 execute 成功后调用 onComplete（如果定义）
    - 在 execute 失败时调用 onError（如果定义）
    - 在用户取消时调用 onCancel（如果定义）
    - _Requirements: 7.1, 7.2, 7.3, 7.4_
  
  - [ ] 6.3 优化错误处理逻辑
    - 统一捕获所有 Handler 错误
    - 使用 errorUtils 进行错误分类和格式化
    - 保持原有的错误消息格式
    - _Requirements: 2.4, 3.5_
  
  - [ ] 6.4 优化状态管理逻辑
    - 确保所有状态更新在 useChat 中
    - 通过回调函数传递更新给 Handler
    - 保持原有的状态更新时序
    - _Requirements: 2.5, 4.4_
  
  - [ ]* 6.5 编写 useChat 的属性测试
    - **Property 2: 策略委托正确性** - 验证正确调用 Handler
    - **Property 4: 无条件分支** - 验证不包含 mode 判断的 if-else
    - **Property 6: 错误处理集中性** - 验证错误统一处理
    - **Property 7: 状态管理集中性** - 验证状态更新在协调者层
    - **Property 19: 生命周期钩子调用** - 验证钩子正确调用
    - **Validates: Requirements 1.2, 2.1, 2.4, 2.5, 7.1, 7.2, 7.3**
  
  - [ ]* 6.6 编写 useChat 的单元测试
    - 测试 sendMessage() 正确选择 Handler
    - 测试状态管理逻辑
    - 测试错误处理逻辑
    - 测试文件上传逻辑
    - _Requirements: 1.2, 2.4, 2.5_

- [ ] 7. 向后兼容性验证
  - [ ] 7.1 创建回归测试套件
    - 为每个现有模式创建测试用例
    - 使用真实的输入数据
    - 对比重构前后的输出
    - _Requirements: 4.1, 4.3, 4.5_
  
  - [ ]* 7.2 编写向后兼容性属性测试
    - **Property 12: 行为向后兼容** - 验证重构后行为一致
    - **Property 13: 消息格式兼容** - 验证消息结构相同
    - **Property 14: 状态更新时序一致** - 验证状态更新顺序相同
    - **Property 15: 附件处理兼容** - 验证附件处理逻辑相同
    - **Validates: Requirements 4.1, 4.3, 4.4, 4.5**
  
  - [ ] 7.3 验证 API 签名不变
    - 检查 sendMessage 的参数类型
    - 检查返回的 Hook 接口
    - 确保完全向后兼容
    - _Requirements: 4.2_

- [ ] 8. 代码质量和文档
  - [ ] 8.1 添加 TypeScript 类型注解
    - 为所有函数添加类型注解
    - 为所有变量添加类型注解
    - 消除所有 any 类型
    - _Requirements: 5.4_
  
  - [ ] 8.2 添加 JSDoc 注释
    - 为所有接口添加文档注释
    - 为所有类添加文档注释
    - 为所有公共方法添加文档注释
    - _Requirements: 5.2_
  
  - [ ] 8.3 添加代码注释
    - 在 sendMessage 中添加步骤注释
    - 在关键逻辑处添加解释注释
    - 在复杂算法处添加说明注释
    - _Requirements: 5.3_
  
  - [ ]* 8.4 编写代码质量属性测试
    - **Property 16: 类型注解完整性** - 验证所有代码有类型注解
    - **Property 3: 代码封装性** - 验证 Handler 不包含其他模式逻辑
    - **Validates: Requirements 5.4, 1.3**

- [ ] 9. 性能和优化
  - [ ] 9.1 优化策略查找性能
    - 确认使用 Map 数据结构
    - 在模块加载时完成注册
    - 避免运行时创建 Handler 实例
    - _Requirements: 1.4_
  
  - [ ] 9.2 优化内存占用
    - 复用 Handler 实例
    - 避免不必要的对象创建
    - 及时清理不再使用的资源
    - _Requirements: 7.5_
  
  - [ ]* 9.3 性能回归测试
    - 对比重构前后的性能指标
    - 确保没有性能退化
    - _Requirements: 4.1_

- [ ] 10. 最终检查点
  - [ ] 10.1 运行所有测试
    - 运行单元测试
    - 运行属性测试
    - 运行集成测试
    - 运行回归测试
    - 确保所有测试通过
  
  - [ ] 10.2 代码审查
    - 检查代码风格一致性
    - 检查命名规范
    - 检查注释完整性
    - 检查类型安全性
  
  - [ ] 10.3 文档更新
    - 更新 README（如果需要）
    - 更新架构文档
    - 更新 API 文档
  
  - [ ] 10.4 用户验收
    - 在开发环境测试所有功能
    - 验证用户体验没有变化
    - 收集反馈并修复问题
