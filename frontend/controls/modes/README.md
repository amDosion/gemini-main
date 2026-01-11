# Modes 模式控制组件目录

本目录存放各 AppMode 对应的控制组件。

## 文件说明

| 文件 | 对应模式 | 控制项 |
|------|---------|--------|
| `ChatControls.tsx` | chat | Search, Browse, RAG, Cache, Reasoning, URL Context, Code |
| `ImageGenControls.tsx` | image-gen | Style, Count, Aspect Ratio, Resolution, Advanced |
| `ImageEditControls.tsx` | image-edit | Try-On, Aspect Ratio, Resolution, Advanced |
| `ImageOutpaintControls.tsx` | image-outpainting | Scale/Offset Mode, Parameters |
| `VideoGenControls.tsx` | video-gen | Aspect Ratio, Resolution |
| `AudioGenControls.tsx` | audio-gen | Voice |
| `VirtualTryOnControls.tsx` | virtual-try-on | Clothing Type, Mask Preview |
| `PdfExtractControls.tsx` | pdf-extract | Template, Advanced |

## 新增模式

1. 在本目录创建 `XxxControls.tsx`
2. 在 `../index.ts` 中导出
3. 在 `ModeControlsCoordinator` 中添加 case 分支
