/**
 * 分层设计类型定义
 *
 * LayerDoc 分层文档结构，用于前端图层编辑和后端渲染
 */

// =========================
// Transform
// =========================
export interface Transform {
  x: number;
  y: number;
  scale: number;
  rotate: number;
  anchorX: number;
  anchorY: number;
}

// =========================
// Layer Types
// =========================
export type BlendMode = 'normal' | 'multiply' | 'screen' | 'overlay';

export interface BaseLayer {
  id: string;
  name?: string;
  type: 'raster' | 'text' | 'shape' | 'gradient';
  z: number;
  opacity: number;
  blend: BlendMode;
  transform: Transform;
}

export interface RasterLayer extends BaseLayer {
  type: 'raster';
  pngBase64?: string;
  assetUrl?: string;
  maskPngBase64?: string;
  maskSvgPath?: string;
}

export interface TextStyle {
  fontSize: number;
  fontColor: string;
  strokeColor?: string;
  strokeWidth?: number;
  align: 'left' | 'center' | 'right';
  lineSpacing?: number;
  fitToBox?: boolean;
  shadowColor?: string;
  shadowDx?: number;
  shadowDy?: number;
  shadowBlur?: number;
}

export interface TextLayer extends BaseLayer {
  type: 'text';
  text: string;
  bbox: [number, number, number, number]; // [x, y, width, height]
  style: TextStyle;
  boxFill?: string;
  boxRadius?: number;
  boxPadding?: number;
}

export interface ShapeStyle {
  fill?: string;
  stroke?: string;
  strokeWidth?: number;
  radius?: number;
  gradient?: Record<string, unknown>;
}

export type ShapeType = 'rect' | 'roundRect' | 'ellipse' | 'path';

export interface ShapeLayer extends BaseLayer {
  type: 'shape';
  shape: ShapeType;
  bbox: [number, number, number, number]; // [x, y, width, height]
  style: ShapeStyle;
  svgPathD?: string;
}

export interface GradientStop {
  position: number;
  color: string;
}

export interface GradientLayer extends BaseLayer {
  type: 'gradient';
  angle: number;
  stops: [number, string][]; // [[position, color], ...]
}

export type Layer = RasterLayer | TextLayer | ShapeLayer | GradientLayer;

// =========================
// LayerDoc
// =========================
export interface LayerDoc {
  width: number;
  height: number;
  background?: string;
  layers: Layer[];
}

// =========================
// API Response Types
// =========================
export interface LayeredSuggestResponse {
  success: boolean;
  layerDoc?: LayerDoc;
  error?: string;
}

export interface DecomposedLayer {
  id: string;
  name: string;
  z: number;
  pngBase64: string;
  width: number;
  height: number;
}

export interface LayeredDecomposeResponse {
  success: boolean;
  layers?: DecomposedLayer[];
  total?: number;
  seed?: number;
  error?: string;
  code?: string; // e.g., 'SERVICE_NOT_AVAILABLE'
}

export interface VectorPath {
  id: string;
  d: string;
  pointsCount: number;
}

export interface LayeredVectorizeResponse {
  success: boolean;
  svg?: string;
  svgBase64?: string;
  paths?: VectorPath[];
  width?: number;
  height?: number;
  contoursCount?: number;
  error?: string;
}

export interface LayeredRenderResponse {
  success: boolean;
  imageBase64?: string;
  mimeType?: string;
  width?: number;
  height?: number;
  error?: string;
}

// =========================
// Mode Types
// =========================
export type LayeredDesignMode =
  | 'image-layered-suggest'
  | 'image-layered-decompose'
  | 'image-layered-vectorize'
  | 'image-layered-render';

// =========================
// Request Options
// =========================
export interface SuggestLayoutOptions {
  canvasW?: number;
  canvasH?: number;
  maxTextBoxes?: number;
  modelId?: string;
  locale?: string;
}

export interface DecomposeOptions {
  layers?: number;
  seed?: number;
  prompt?: string;
}

export interface VectorizeOptions {
  simplifyTolerance?: number;
  smoothIterations?: number;
  useBezier?: boolean;
  bezierSmoothness?: number;
  threshold?: number;
  blurRadius?: number;
}

// =========================
// Hook State
// =========================
export interface LayeredDesignState {
  loading: boolean;
  layerDoc: LayerDoc | null;
  renderedImage: string | null;
  error: string | null;
}
