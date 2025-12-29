# Implementation Plan: 图片生成功能增强

## Overview

本实现计划将图片生成功能增强分为三个主要阶段：
1. 配置层重构（`constants.ts`）
2. UI 组件更新
3. 服务层多图片支持

所有比例和分辨率配置集中在 `constants.ts`，后续扩展只需修改此文件。

## Tasks

- [x] 1. 重构 `constants.ts` 配置文件
  - [x] 1.1 添加 `z-image-turbo` 模型分辨率映射
    - 添加 `Z_IMAGE_1K_RESOLUTIONS` 映射（11 种比例）
    - 添加 `Z_IMAGE_1280_RESOLUTIONS` 映射（11 种比例）
    - 添加 `Z_IMAGE_1536_RESOLUTIONS` 映射（11 种比例）
    - 添加 `Z_IMAGE_2K_RESOLUTIONS` 映射（11 种比例）
    - 添加详细注释说明每个映射的用途
    - _Requirements: 2.3_

  - [x] 1.2 添加 `wan2.6-image` 模型分辨率映射
    - 添加 `WAN26_IMAGE_RESOLUTIONS` 映射（10 种比例）
    - 添加注释说明像素范围限制
    - _Requirements: 2.4_

  - [x] 1.3 添加 Google 提供商分辨率映射
    - 添加 `GOOGLE_GEN_1K_RESOLUTIONS` 映射（10 种比例）
    - 添加 `GOOGLE_GEN_2K_RESOLUTIONS` 映射（10 种比例）
    - 添加 `GOOGLE_GEN_4K_RESOLUTIONS` 映射（10 种比例）
    - 添加详细注释说明
    - _Requirements: 3.2, 3.3, 3.4_

  - [x] 1.4 添加辅助函数
    - 实现 `getPixelResolution(aspectRatio, tier, provider, modelId)` 函数
    - 实现 `getAspectRatioLabel(aspectRatio, tier, provider, modelId)` 函数
    - 实现 `getAvailableAspectRatios(provider, modelId)` 函数
    - 实现 `getAvailableResolutionTiers(provider, modelId)` 函数
    - 添加详细 JSDoc 注释
    - _Requirements: 6.6, 7.2, 7.3, 7.4_

  - [x] 1.5 更新比例选项配置
    - 添加 `Z_IMAGE_ASPECT_RATIOS` 选项（含 7:9, 9:7, 9:21）
    - 添加 `WAN26_IMAGE_ASPECT_RATIOS` 选项（含 1:4, 4:1）
    - 更新 `GOOGLE_GEN_ASPECT_RATIOS` 选项（10 种比例）
    - _Requirements: 2.6, 3.2_

  - [x] 1.6 添加分辨率档位选项配置
    - 添加 `TONGYI_GEN_RESOLUTION_TIERS` 选项（含标签和基准分辨率）
    - 添加 `Z_IMAGE_RESOLUTION_TIERS` 选项（4 档位）
    - 添加 `GOOGLE_GEN_RESOLUTION_TIERS` 选项（3 档位）
    - _Requirements: 4.1, 4.2, 4.3_

- [x] 2. Checkpoint - 配置层完成
  - 确保所有配置正确定义
  - 确保辅助函数正常工作
  - 如有问题请询问用户

- [x] 3. 更新 `TongYiImageGenControls` 组件
  - [x] 3.1 重构比例选择器
    - 使用 `getAvailableAspectRatios()` 获取可用比例
    - 使用 `getAspectRatioLabel()` 显示带像素分辨率的标签
    - 根据模型类型动态显示不同比例选项
    - _Requirements: 2.1, 2.5, 2.6, 2.7_

  - [x] 3.2 重构分辨率档位选择器
    - 使用 `getAvailableResolutionTiers()` 获取可用档位
    - 显示档位标签和基准分辨率
    - 根据模型类型动态显示不同档位选项
    - _Requirements: 4.1_

  - [x] 3.3 添加比例-分辨率联动逻辑
    - 当比例或分辨率档位变化时，更新显示的像素分辨率
    - 确保 UI 实时反映当前选择
    - _Requirements: 2.5_

- [x] 4. 更新 `ImageGenControls` 组件（Google）
  - [x] 4.1 重构比例选择器
    - 使用 `getAvailableAspectRatios('google')` 获取可用比例
    - 使用 `getAspectRatioLabel()` 显示带像素分辨率的标签
    - _Requirements: 3.1, 3.5_

  - [x] 4.2 重构分辨率档位选择器
    - 使用 `getAvailableResolutionTiers('google')` 获取可用档位
    - 显示档位标签和基准分辨率
    - _Requirements: 4.2_

  - [x] 4.3 添加比例-分辨率联动逻辑
    - 当比例或分辨率档位变化时，更新显示的像素分辨率
    - _Requirements: 3.4_

- [x] 5. Checkpoint - UI 组件完成
  - 确保通义和谷歌提供商的比例-分辨率联动正常工作
  - 确保不同模型显示正确的选项
  - 如有问题请询问用户

- [x] 6. 更新 `tongyi/image-gen.ts` 服务
  - [x] 6.1 更新 `generateWanV2Image` 函数
    - 使用 `getPixelResolution()` 获取像素分辨率
    - 确保 `n` 参数正确传递
    - _Requirements: 1.1_

  - [x] 6.2 更新 `generateZImage` 函数
    - 使用 `getPixelResolution()` 获取像素分辨率
    - 确保 `n` 参数正确传递（z-image-turbo 限制为 1）
    - _Requirements: 1.3, 1.4_

  - [x] 6.3 实现多图片响应解析
    - 实现 `parseMultipleImages()` 函数
    - 遍历 `output.choices` 提取所有图片
    - 返回 `ImageGenerationResult[]` 数组
    - _Requirements: 1.2, 5.1, 5.2, 5.3, 5.4_

  - [x] 6.4 更新返回值处理
    - 修改 `generateWanV2Image` 返回多张图片
    - 修改 `generateZImage` 返回多张图片
    - _Requirements: 1.2_

- [x] 7. Checkpoint - 服务层完成
  - 确保多图片生成正常工作
  - 确保响应解析正确
  - 如有问题请询问用户

- [x] 8. 添加单元测试
  - [x] 8.1 测试辅助函数
    - 测试 `getPixelResolution()` 各种输入组合
    - 测试 `getAspectRatioLabel()` 格式正确性
    - 测试 `getAvailableAspectRatios()` 返回正确选项
    - 测试 `getAvailableResolutionTiers()` 返回正确选项
    - _Requirements: 6.6, 7.2, 7.3, 7.4_

  - [x] 8.2 测试多图片解析
    - 测试 `parseMultipleImages()` 正确解析响应
    - 测试边界条件（0 张、1 张、4 张图片）
    - _Requirements: 5.1, 5.2, 5.3_

- [x] 9. Final Checkpoint - 功能完成
  - 所有测试通过（37 个新增测试）
  - 功能正常工作

## Notes

- 每个任务引用了具体的需求编号以便追溯
- Checkpoint 任务用于阶段性验证
- 所有配置修改集中在 `constants.ts`，便于后续维护
- 单元测试为必需任务，确保代码质量
