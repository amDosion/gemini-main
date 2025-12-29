# Requirements Document

## Introduction

本文档定义了图片生成功能的增强需求，涉及 `tongyi`（通义）和 `google` 两个提供商。主要解决以下问题：
1. `wan2.6-t2i` 等模型支持 `n` 参数生成多张图片，但当前实现只返回第一张
2. 比例选择与分辨率显示应该联动，选择比例后自动显示对应的像素分辨率
3. 所有比例和分辨率配置应集中在 `constants.ts` 文件中，便于后续扩展维护

## Glossary

- **TongYi_Provider**: 通义提供商，即阿里云 `DashScope` 服务
- **Google_Provider**: 谷歌提供商，使用 `Google GenAI` 服务
- **WanV2_T2I_Model**: 万相 V2 系列文生图模型，包括 `wan2.6-t2i`、`wan2.5-t2i-preview` 等
- **Imagen_Model**: 谷歌 `Imagen` 系列图片生成模型
- **Aspect_Ratio**: 图片宽高比例，如 `1:1`、`16:9` 等
- **Resolution_Tier**: 分辨率档位，如 `1K`、`1.25K`、`1.5K`（通义）或 `1K`、`2K`（谷歌）
- **Pixel_Resolution**: 实际像素分辨率，如 `1280*1280`、`1280*720` 等
- **N_Parameter**: API 的 `n` 参数，控制生成图片数量
- **Constants_File**: `frontend/controls/constants.ts` 配置文件，集中管理所有比例和分辨率配置

## Requirements

### Requirement 1: 多图片生成支持

**User Story:** As a user, I want to generate multiple images in a single request when using `wan2.6-t2i` model, so that I can get more options to choose from.

#### Acceptance Criteria

1. WHEN a user selects `numberOfImages > 1` AND uses `wan2.6-t2i` model, THE TongYi_Provider SHALL send `n` parameter to the API with the selected count
2. WHEN the API returns multiple images in `output.choices`, THE TongYi_Provider SHALL extract all images and return them as an array
3. WHEN `z-image-turbo` model is selected, THE System SHALL limit `numberOfImages` to 1 and disable the count selector
4. WHEN other `WanV2_T2I_Model` models are selected, THE System SHALL allow `numberOfImages` from 1 to 4

### Requirement 2: 通义比例与分辨率联动显示

**User Story:** As a user, I want to see the actual pixel resolution when I select an aspect ratio in TongYi provider, so that I know exactly what size image will be generated.

#### Acceptance Criteria

1. WHEN a user selects an `Aspect_Ratio` in TongYi provider, THE TongYiImageGenControls SHALL display the corresponding `Pixel_Resolution` based on the current `Resolution_Tier` and model type

2. FOR `wan2.x-t2i` series models (wan2.6-t2i, wan2.5-t2i-preview, etc.), THE System SHALL use the following mapping:
   
   **1K 分辨率：**
   - `1:1` → `1280*1280`
   - `2:3` → `800*1200`
   - `3:2` → `1200*800`
   - `3:4` → `960*1280`
   - `4:3` → `1280*960`
   - `9:16` → `720*1280`
   - `16:9` → `1280*720`
   - `21:9` → `1344*576`
   
   **1.25K 分辨率：**
   - `1:1` → `1440*1440`
   - `2:3` → `900*1350`
   - `3:2` → `1350*900`
   - `3:4` → `1080*1440`
   - `4:3` → `1440*1080`
   - `9:16` → `810*1440`
   - `16:9` → `1440*810`
   - `21:9` → `1512*648`
   
   **1.5K 分辨率：**
   - `1:1` → `1536*1536`
   - `2:3` → `960*1440`
   - `3:2` → `1440*960`
   - `3:4` → `1152*1536`
   - `4:3` → `1536*1152`
   - `9:16` → `864*1536`
   - `16:9` → `1536*864`
   - `21:9` → `1680*720`

3. FOR `z-image-turbo` model, THE System SHALL use the following mapping with additional aspect ratios:
   
   **注意：** `z-image-turbo` 模型总像素范围为 [512×512, 2048×2048]，推荐范围 [1024×1024, 1536×1536]
   
   **1K 分辨率（基准 1024×1024 总像素）：**
   - `1:1` → `1024*1024`
   - `2:3` → `832*1248`
   - `3:2` → `1248*832`
   - `3:4` → `864*1152`
   - `4:3` → `1152*864`
   - `7:9` → `896*1152`
   - `9:7` → `1152*896`
   - `9:16` → `720*1280`
   - `9:21` → `576*1344`
   - `16:9` → `1280*720`
   - `21:9` → `1344*576`
   
   **1.25K 分辨率（基准 1280×1280 总像素）：**
   - `1:1` → `1280*1280`
   - `2:3` → `1024*1536`
   - `3:2` → `1536*1024`
   - `3:4` → `1104*1472`
   - `4:3` → `1472*1104`
   - `7:9` → `1120*1440`
   - `9:7` → `1440*1120`
   - `9:16` → `864*1536`
   - `9:21` → `720*1680`
   - `16:9` → `1536*864`
   - `21:9` → `1680*720`
   
   **1.5K 分辨率（基准 1536×1536 总像素，推荐）：**
   - `1:1` → `1536*1536`
   - `2:3` → `1248*1872`
   - `3:2` → `1872*1248`
   - `3:4` → `1296*1728`
   - `4:3` → `1728*1296`
   - `7:9` → `1344*1728`
   - `9:7` → `1728*1344`
   - `9:16` → `1152*2048`
   - `9:21` → `864*2016`
   - `16:9` → `2048*1152`
   - `21:9` → `2016*864`
   
   **2K 分辨率（基准 2048×2048 总像素，最大）：**
   - `1:1` → `2048*2048`
   - `2:3` → `1664*2496`
   - `3:2` → `2496*1664`
   - `3:4` → `1728*2304`
   - `4:3` → `2304*1728`
   - `7:9` → `1792*2304`
   - `9:7` → `2304*1792`
   - `9:16` → `1536*2730`
   - `9:21` → `1152*2688`
   - `16:9` → `2730*1536`
   - `21:9` → `2688*1152`

4. FOR `wan2.6-image` model (image editing mode), THE System SHALL use the following mapping:
   
   **注意：** `wan2.6-image` 模型总像素范围为 [589824, 1638400]（即 768×768 至 1280×1280），宽高比范围为 [1:4, 4:1]
   
   **标准分辨率（单档位）：**
   - `1:1` → `1280*1280` 或 `1024*1024`
   - `2:3` → `800*1200`
   - `3:2` → `1200*800`
   - `3:4` → `960*1280`
   - `4:3` → `1280*960`
   - `9:16` → `720*1280`
   - `16:9` → `1280*720`
   - `21:9` → `1344*576`
   - `1:4` → `768*2700` (极端竖向)
   - `4:1` → `2700*768` (极端横向)

5. WHEN the user changes `Resolution_Tier`, THE System SHALL update the displayed `Pixel_Resolution` accordingly
6. THE Aspect_Ratio selector SHALL display both the ratio label and the corresponding pixel resolution (e.g., "1:1 (1280×1280)")
7. THE System SHALL dynamically show different aspect ratio options based on the selected model

### Requirement 3: 谷歌比例与分辨率联动显示

**User Story:** As a user, I want to see the actual pixel resolution when I select an aspect ratio in Google provider, so that I know exactly what size image will be generated.

#### Acceptance Criteria

1. WHEN a user selects an `Aspect_Ratio` in Google provider, THE ImageGenControls SHALL display the corresponding `Pixel_Resolution` based on the current `Resolution_Tier`
2. THE System SHALL support the following aspect ratios for Google provider:
   - `1:1` (Square)
   - `2:3` (Portrait)
   - `3:2` (Landscape)
   - `3:4` (Portrait)
   - `4:3` (Landscape)
   - `4:5` (Portrait)
   - `5:4` (Landscape)
   - `9:16` (Portrait)
   - `16:9` (Landscape)
   - `21:9` (Ultrawide)

3. THE System SHALL define pixel resolution mappings for Google provider with three resolution tiers:
   
   **1K (Standard) 分辨率：**
   - `1:1` → `1024×1024`
   - `2:3` → `682×1024`
   - `3:2` → `1024×682`
   - `3:4` → `768×1024`
   - `4:3` → `1024×768`
   - `4:5` → `819×1024`
   - `5:4` → `1024×819`
   - `9:16` → `576×1024`
   - `16:9` → `1024×576`
   - `21:9` → `1024×438`
   
   **2K (High) 分辨率：**
   - `1:1` → `2048×2048`
   - `2:3` → `1365×2048`
   - `3:2` → `2048×1365`
   - `3:4` → `1536×2048`
   - `4:3` → `2048×1536`
   - `4:5` → `1638×2048`
   - `5:4` → `2048×1638`
   - `9:16` → `1152×2048`
   - `16:9` → `2048×1152`
   - `21:9` → `2048×877`
   
   **4K (Ultra) 分辨率：**
   - `1:1` → `4096×4096`
   - `2:3` → `2730×4096`
   - `3:2` → `4096×2730`
   - `3:4` → `3072×4096`
   - `4:3` → `4096×3072`
   - `4:5` → `3276×4096`
   - `5:4` → `4096×3276`
   - `9:16` → `2304×4096`
   - `16:9` → `4096×2304`
   - `21:9` → `4096×1755`

4. WHEN the user changes `Resolution_Tier`, THE System SHALL update the displayed `Pixel_Resolution` accordingly
5. THE Aspect_Ratio selector SHALL display both the ratio label and the corresponding pixel resolution (e.g., "1:1 (1024×1024)")
6. THE constants file SHALL include `GOOGLE_GEN_1K_RESOLUTIONS`, `GOOGLE_GEN_2K_RESOLUTIONS`, `GOOGLE_GEN_4K_RESOLUTIONS` mappings

### Requirement 4: 分辨率档位选择器优化

**User Story:** As a user, I want the resolution tier selector to show meaningful information, so that I understand what each option means.

#### Acceptance Criteria

1. FOR TongYi provider, THE Resolution_Tier selector SHALL display the base resolution for each tier:
   - `1K` → "1K (1280×1280 base)"
   - `1.25K` → "1.25K (1440×1440 base)"
   - `1.5K` → "1.5K (1536×1536 base)"
2. FOR Google provider, THE Resolution_Tier selector SHALL display:
   - `1K` → "1K Standard (1024×1024 base)"
   - `2K` → "2K High (2048×2048 base)"
   - `4K` → "4K Ultra (4096×4096 base)"
3. THE Resolution_Tier options SHALL be defined in Constants_File for each provider

### Requirement 5: API 响应多图片解析

**User Story:** As a developer, I want the system to correctly parse multiple images from the API response, so that all generated images are displayed to the user.

#### Acceptance Criteria

1. WHEN the API response contains `output.choices` with multiple items, THE System SHALL iterate through all choices and extract images
2. FOR EACH choice in `output.choices`, THE System SHALL extract the image URL from `message.content[].image`
3. THE System SHALL return an array of `ImageGenerationResult` objects, one for each successfully extracted image
4. IF any image extraction fails, THE System SHALL log a warning but continue processing remaining images


### Requirement 6: 配置集中化与可扩展性

**User Story:** As a developer, I want all aspect ratio and resolution configurations centralized in `constants.ts`, so that I can easily add new ratios or resolutions by modifying only one file.

#### Acceptance Criteria

1. THE Constants_File SHALL contain all aspect ratio definitions with their corresponding pixel resolutions
2. THE Constants_File SHALL include detailed comments explaining:
   - The purpose of each configuration section
   - How to add new aspect ratios
   - How to add new resolution tiers
   - The relationship between aspect ratios and pixel resolutions
3. WHEN a new aspect ratio needs to be added, THE developer SHALL only need to modify Constants_File
4. WHEN a new resolution tier needs to be added, THE developer SHALL only need to modify Constants_File
5. THE UI components SHALL dynamically read configurations from Constants_File without hardcoded values
6. THE Constants_File SHALL export helper functions to get pixel resolution by aspect ratio and resolution tier

### Requirement 7: 统一的比例-分辨率数据结构

**User Story:** As a developer, I want a unified data structure for aspect ratio and resolution mapping, so that the code is consistent and maintainable.

#### Acceptance Criteria

1. THE Constants_File SHALL define a unified interface for aspect ratio options:
   ```typescript
   interface AspectRatioOption {
     label: string;           // 显示标签，如 "1:1 Square"
     value: string;           // 比例值，如 "1:1"
     resolutions: {           // 各分辨率档位对应的像素分辨率
       [tier: string]: string; // 如 { "1K": "1280*1280", "1.25K": "1440*1440" }
     };
   }
   ```
2. THE Constants_File SHALL provide `getPixelResolution(aspectRatio, tier, provider)` helper function
3. THE Constants_File SHALL provide `getAspectRatioLabel(aspectRatio, tier, provider)` helper function that returns label with pixel resolution (e.g., "1:1 (1280×1280)")
4. THE UI components SHALL use these helper functions instead of hardcoded mappings
