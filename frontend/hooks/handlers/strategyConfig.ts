/**
 * 策略配置文件
 * 
 * 注册所有 Handler 到 StrategyRegistry
 * 注册所有 Preprocessor 到 PreprocessorRegistry
 */

import { StrategyRegistry } from './StrategyRegistry';
import { PreprocessorRegistry, GoogleFileUploadPreprocessor } from './PreprocessorRegistry';
import { ChatHandler } from './ChatHandlerClass';
import { ImageGenHandler } from './ImageGenHandlerClass';
import { ImageEditHandler } from './ImageEditHandlerClass';
import {
  ImageOutpaintingHandler,
  VirtualTryOnHandler,
  VideoGenHandler,
  AudioGenHandler,
  PdfExtractHandler
} from './AllHandlerClasses';
import { DeepResearchHandler } from './DeepResearchHandler';
import { MultiAgentHandler } from './MultiAgentHandler';

/**
 * 创建并配置全局 StrategyRegistry 实例
 */
export const strategyRegistry = new StrategyRegistry();

// 注册所有 Handler
strategyRegistry.register('chat', new ChatHandler());
strategyRegistry.register('image-gen', new ImageGenHandler());
// 图片编辑模式（已拆分为多个独立模式）
strategyRegistry.register('image-chat-edit', new ImageEditHandler());
strategyRegistry.register('image-mask-edit', new ImageEditHandler());
strategyRegistry.register('image-inpainting', new ImageEditHandler());
strategyRegistry.register('image-background-edit', new ImageEditHandler());
strategyRegistry.register('image-recontext', new ImageEditHandler());
strategyRegistry.register('image-outpainting', new ImageOutpaintingHandler());
strategyRegistry.register('virtual-try-on', new VirtualTryOnHandler());
strategyRegistry.register('video-gen', new VideoGenHandler());
strategyRegistry.register('audio-gen', new AudioGenHandler());
strategyRegistry.register('pdf-extract', new PdfExtractHandler());
strategyRegistry.register('deep-research', new DeepResearchHandler());
strategyRegistry.register('multi-agent', new MultiAgentHandler());

// 锁定注册表，防止运行时动态注册
strategyRegistry.finalize();

/**
 * 创建并配置全局 PreprocessorRegistry 实例
 */
export const preprocessorRegistry = new PreprocessorRegistry();

// 注册 Google 文件上传前置处理器（高优先级）
preprocessorRegistry.register(new GoogleFileUploadPreprocessor());
