/**
 * 模式控件导出
 * 
 * 按提供商分组导出，支持新架构
 */

// 按提供商导出
export * as GoogleControls from './google';
export * as TongYiControls from './tongyi';
export * as OpenAIControls from './openai';

// 向后兼容：默认导出 Google 实现
export { ChatControls } from './google/ChatControls';
export { ImageGenControls } from './google/ImageGenControls';
export { ImageEditControls } from './google/ImageEditControls';
export { ImageOutpaintControls } from './google/ImageOutpaintControls';
export { VideoGenControls } from './google/VideoGenControls';
export { AudioGenControls } from './google/AudioGenControls';
export { VirtualTryOnControls } from './google/VirtualTryOnControls';
export { PdfExtractControls } from './google/PdfExtractControls';
export { DeepResearchControls } from './google/DeepResearchControls';
export { MultiAgentControls } from './google/MultiAgentControls';

// 向后兼容：TongYi 专用控件（已弃用，请使用 TongYiControls.ImageGenControls）
export { ImageGenControls as TongYiImageGenControls } from './tongyi/ImageGenControls';
