# Implementation Plan: Provider Template Smart Switch

## Overview

实现智能 Provider Template 切换功能，允许用户在编辑配置时切换 Provider，系统自动加载对应的已有配置数据（API Key、模型列表、Connection Details 等）。

## Tasks

- [x] 1. 修改 SettingsModal 传递配置列表
  - 修改 `SettingsModal.tsx` 中 EditorTab 的调用
  - 添加 `existingProfiles={profiles}` 参数传递
  - 确保 profiles 数据正确传递到 EditorTab
  - _Requirements: 1.1, 1.2_

- [x] 2. 修改 EditorTab 接收配置列表
  - 更新 `EditorTabProps` 接口定义
  - 移除 `existingProfiles` 参数的"不再使用"注释
  - 在组件中接收并使用 `existingProfiles` 参数
  - _Requirements: 1.2, 1.3_

- [ ] 3. 实现配置查找函数
  - [x] 3.1 创建 `findProviderConfig` 函数
    - 接收 providerId、profiles 数组、可选的 excludeId
    - 过滤出匹配 providerId 的配置
    - 排除 excludeId 指定的配置
    - 返回 updatedAt 最大的配置或 null
    - _Requirements: 2.1, 2.2, 2.3_

  - [ ]* 3.2 编写 findProviderConfig 单元测试
    - 测试找到单个匹配配置
    - 测试找到多个匹配配置，返回最新的
    - 测试未找到匹配配置，返回 null
    - 测试排除当前编辑的配置
    - _Requirements: 2.1, 2.2, 2.3_

  - [ ]* 3.3 编写配置查找确定性属性测试
    - **Property 1: 配置查找的确定性**
    - **Validates: Requirements 2.1, 2.2**
    - 验证相同输入返回相同结果
    - _Requirements: 2.1, 2.2_

  - [ ]* 3.4 编写最近配置优先性属性测试
    - **Property 6: 最近配置优先性**
    - **Validates: Requirements 2.2**
    - 验证返回 updatedAt 最大的配置
    - _Requirements: 2.2_

- [ ] 4. 实现编辑模式的智能切换
  - [x] 4.1 修改 Provider Template 点击处理器（编辑模式）
    - 在 onClick 中调用 findProviderConfig 查找配置
    - 如果找到配置，加载所有字段到 formData
    - 如果找到配置，更新 verifiedModels 为 savedModels
    - 如果未找到配置，应用模板默认值并清空用户数据
    - 添加控制台日志输出切换信息
    - _Requirements: 3.1, 3.2, 3.3, 3.4_

  - [ ]* 4.2 编写编辑模式切换单元测试
    - 测试切换到已有配置，加载所有数据
    - 测试切换到不存在的 Provider，应用默认值
    - 测试 verifiedModels 正确更新
    - _Requirements: 3.1, 3.2, 3.3_

  - [ ]* 4.3 编写编辑模式数据完整性属性测试
    - **Property 2: 编辑模式数据完整性**
    - **Validates: Requirements 3.1, 3.2, 6.1, 6.2**
    - 验证加载后的 formData 包含原配置的所有字段
    - _Requirements: 3.1, 3.2, 6.1, 6.2_

  - [ ]* 4.4 编写模型列表同步性属性测试
    - **Property 4: 模型列表同步性**
    - **Validates: Requirements 3.2, 4.1, 5.2**
    - 验证 verifiedModels 与 formData.savedModels 一致
    - _Requirements: 3.2, 4.1, 5.2_

- [ ] 5. 实现创建模式的智能切换
  - [x] 5.1 修改 Provider Template 点击处理器（创建模式）
    - 在 onClick 中调用 findProviderConfig 查找配置
    - 如果找到配置，复制数据字段但保持当前 id
    - 如果找到配置，更新 name 为模板名称
    - 如果找到配置，更新 verifiedModels 为 savedModels
    - 如果未找到配置，应用模板默认值
    - 添加控制台日志输出创建信息
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [ ]* 5.2 编写创建模式切换单元测试
    - 测试基于已有配置创建，保持新 id
    - 测试切换到不存在的 Provider，应用默认值
    - 测试 name 字段正确更新
    - _Requirements: 4.1, 4.2, 4.3, 4.4_

  - [ ]* 5.3 编写创建模式 ID 独立性属性测试
    - **Property 3: 创建模式 ID 独立性**
    - **Validates: Requirements 4.2**
    - 验证新配置的 id 与原配置不同
    - _Requirements: 4.2_

- [x] 6. 添加错误处理和日志
  - 在配置查找中添加 try-catch
  - 在状态更新中添加错误处理
  - 添加开发环境的详细日志
  - 添加生产环境的精简日志
  - _Requirements: 6.3, 6.4_

- [ ] 7. 性能优化（可选）
  - [ ]* 7.1 实现 providerConfigCache
    - 使用 useMemo 创建 providerId → ConfigProfile 映射
    - 优化大量配置时的查找性能
    - _Requirements: 7.1_

  - [ ]* 7.2 性能测试
    - 测试 100+ 配置时的切换性能
    - 验证切换操作在 100ms 内完成
    - _Requirements: 7.3_

- [ ] 8. 集成测试
  - [ ]* 8.1 完整切换流程测试
    - 渲染 SettingsModal 和 EditorTab
    - 模拟点击 Provider Template 按钮
    - 验证表单字段和模型列表更新
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [ ]* 8.2 保存后验证测试
    - 切换 Provider 并修改数据
    - 保存配置
    - 验证保存的数据正确
    - _Requirements: 3.4, 4.5_

- [ ] 9. 向后兼容性验证
  - [ ]* 9.1 测试 existingProfiles 未提供的情况
    - 验证降级到原有行为
    - 确保不会崩溃或报错
    - _Requirements: 8.1_

  - [ ]* 9.2 测试与现有功能的兼容性
    - 验证保存功能正常
    - 验证验证功能正常
    - 验证关闭功能正常
    - _Requirements: 8.2, 8.3_

- [x] 10. Checkpoint - 确保所有测试通过
  - 确保所有测试通过，询问用户是否有问题

## Notes

- 任务标记 `*` 的为可选任务，可以跳过以加快 MVP 开发
- 每个任务都引用了具体的需求编号，便于追溯
- 属性测试使用 fast-check 库，每个测试运行 100 次迭代
- 单元测试和属性测试是互补的，都很重要
- 性能优化任务可以在基础功能完成后再进行
