# Implementation Plan: Google Image API 方式梳理与实现

## Overview

本实现计划将在现有的 `imagen_vertex_ai.py` 中添加 `edit_image()` 支持，同时保持向后兼容性。实现将遵循设计文档中定义的架构和接口。

## Tasks

- [ ] 1. 添加 Capability 模型常量和路由逻辑
  - 在 `imagen_vertex_ai.py` 顶部添加 `CAPABILITY_MODELS` 常量集合
  - 更新 `_determine_api_method()` 方法以支持 capability 模型路由
  - 添加单元测试验证路由逻辑
  - _Requirements: 8.1_

- [ ]* 1.1 编写路由逻辑的属性测试
  - **Property 1: Model Routing Correctness**
  - **Validates: Requirements 8.1**
  - 使用 Hypothesis 生成随机模型名称
  - 验证 capability 模型正确路由到 edit_image
  - 验证 Gemini/Veo 模型正确路由到 generate_content
  - 验证 Imagen 模型正确路由到 generate_images

- [ ] 2. 实现 Reference Image 构建器
  - [ ] 2.1 创建 `_build_raw_reference_image()` 方法
    - 接受 image_bytes 参数
    - 返回 `types.RawReferenceImage` 对象
    - _Requirements: 8.3_

  - [ ] 2.2 创建 `_build_mask_reference_image()` 方法
    - 接受 mask_bytes, mask_mode, mask_dilation 参数
    - 支持三种 mask 模式（FOREGROUND, BACKGROUND, USER_PROVIDED）
    - 返回 `types.MaskReferenceImage` 对象
    - _Requirements: 8.4_

  - [ ] 2.3 创建 `_build_style_reference_image()` 方法（可选）
    - 接受 image_bytes, style_description 参数
    - 返回 `types.StyleReferenceImage` 对象
    - _Requirements: 8.3_

  - [ ] 2.4 创建 `_build_subject_reference_image()` 方法（可选）
    - 接受 image_bytes, subject_type, subject_description 参数
    - 返回 `types.SubjectReferenceImage` 对象
    - _Requirements: 8.3_

- [ ]* 2.5 编写 Reference Image 组合的属性测试
  - **Property 3: Reference Image Combination**
  - **Validates: Requirements 8.3**
  - 使用 Hypothesis 生成随机的 Reference Image 组合
  - 验证每种组合都能正确构建

- [ ]* 2.6 编写 Mask 处理的属性测试
  - **Property 4: Mask Processing**
  - **Validates: Requirements 8.4**
  - 使用 Hypothesis 生成随机的 mask 配置
  - 验证 mask_mode 和 mask_dilation 正确设置

- [ ] 3. 实现 EditImageConfig 构建器
  - 创建 `_build_edit_config()` 方法
  - 支持所有 EditImageConfig 参数
  - 设置合理的默认值
  - 验证参数范围（如 guidance_scale, mask_dilation）
  - _Requirements: 8.2_

- [ ]* 3.1 编写编辑模式的属性测试
  - **Property 2: Edit Mode Support**
  - **Validates: Requirements 8.2**
  - 使用 Hypothesis 生成随机的编辑模式
  - 验证每种模式都能正确配置

- [ ] 4. 实现核心 edit_image 方法
  - [ ] 4.1 创建 `_edit_with_capability()` 私有方法
    - 接受 model, prompt, reference_images, config 参数
    - 调用 `self._client.models.edit_image()`
    - 处理 API 响应
    - 提取生成的图片
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [ ] 4.2 创建 `edit()` 公共方法
    - 接受 model, prompt, base_image, mask_image 等参数
    - 验证模型是否为 capability 模型
    - 构建 Reference Images
    - 构建 EditImageConfig
    - 调用 `_edit_with_capability()`
    - 返回统一格式的结果
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

- [ ] 5. 更新 generate() 方法以支持路由
  - 在 `generate()` 方法中添加 capability 模型检测
  - 如果是 capability 模型且提供了 base_image，路由到 `edit()`
  - 保持现有 Imagen 和 Gemini 模型的行为不变
  - _Requirements: 8.5_

- [ ]* 5.1 编写向后兼容性的属性测试
  - **Property 5: Backward Compatibility**
  - **Validates: Requirements 8.5**
  - 使用 Hypothesis 生成随机的旧版本调用
  - 验证 Imagen 和 Gemini 模型的行为不变

- [ ] 6. 添加错误处理
  - [ ] 6.1 添加模型验证
    - 验证 edit() 方法只接受 capability 模型
    - 抛出清晰的错误消息
    - _Requirements: 8.1_

  - [ ] 6.2 添加 Reference Image 验证
    - 验证必需的 Reference Image 存在
    - 验证 mask_mode 与 mask_image 的一致性
    - _Requirements: 8.3, 8.4_

  - [ ] 6.3 添加 API 错误处理
    - 捕获 Vertex AI API 错误
    - 包装为统一的 APIError
    - 记录详细的错误日志
    - _Requirements: 8.1_

- [ ] 7. 更新类型注解和文档字符串
  - 为所有新方法添加完整的类型注解
  - 添加详细的文档字符串
  - 包含参数说明和示例
  - _Requirements: 8.1, 8.2, 8.3, 8.4_

- [ ] 8. Checkpoint - 确保所有测试通过
  - 运行所有单元测试
  - 运行所有属性测试
  - 确保代码覆盖率 > 80%
  - 询问用户是否有问题

- [ ] 9. 创建集成测试
  - [ ] 9.1 创建 `test_edit_image_integration.py`
    - 测试 INPAINT_INSERTION 模式
    - 测试 INPAINT_REMOVAL 模式
    - 测试 OUTPAINT 模式
    - 使用真实的 Vertex AI API
    - _Requirements: 8.2_

  - [ ] 9.2 测试不同的 Reference Image 组合
    - 测试 Raw + Mask
    - 测试 Raw + Mask + Style
    - 测试 Raw + Mask + Subject
    - _Requirements: 8.3_

  - [ ] 9.3 测试不同的 Mask 模式
    - 测试 FOREGROUND 模式
    - 测试 BACKGROUND 模式
    - 测试 USER_PROVIDED 模式
    - _Requirements: 8.4_

- [ ]* 9.4 编写集成测试的属性测试
  - 使用 Hypothesis 生成随机的编辑请求
  - 验证 API 调用成功
  - 验证返回的图片格式正确

- [ ] 10. 更新 API 路由层
  - 在 FastAPI 路由中添加 `/edit-image` 端点
  - 接受 base_image 和 mask_image 的上传
  - 调用 `VertexAIImageGenerator.edit()`
  - 返回编辑后的图片
  - _Requirements: 8.1_

- [ ] 11. 创建使用示例和文档
  - 创建 `EDIT_IMAGE_GUIDE.md` 文档
  - 包含三种 API 方式的对比
  - 包含 edit_image 的完整示例
  - 包含常见问题解答
  - _Requirements: 所有需求_

- [ ] 12. Final Checkpoint - 完整验证
  - 运行所有测试（单元 + 属性 + 集成）
  - 验证向后兼容性
  - 验证文档完整性
  - 询问用户是否满意

## Notes

- 任务标记 `*` 的为可选任务，可以跳过以加快 MVP 开发
- 每个任务都引用了具体的需求编号
- Checkpoint 任务确保增量验证
- 属性测试使用 Hypothesis 库，最少运行 100 次迭代
- 集成测试需要真实的 Vertex AI 凭证
