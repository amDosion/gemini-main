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
  anchor_x: number;
  anchor_y: number;
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
  png_base64?: string;
  asset_url?: string;
  mask_png_base64?: string;
  mask_svg_path?: string;
}

export interface TextStyle {
  font_size: number;
  font_color: string;
  stroke_color?: string;
  stroke_width?: number;
  align: 'left' | 'center' | 'right';
  line_spacing?: number;
  fit_to_box?: boolean;
  shadow_color?: string;
  shadow_dx?: number;
  shadow_dy?: number;
  shadow_blur?: number;
}

export interface TextLayer extends BaseLayer {
  type: 'text';
  text: string;
  bbox: [number, number, number, number]; // [x, y, width, height]
  style: TextStyle;
  box_fill?: string;
  box_radius?: number;
  box_padding?: number;
}

export interface ShapeStyle {
  fill?: string;
  stroke?: string;
  stroke_width?: number;
  radius?: number;
  gradient?: Record<string, unknown>;
}

export type ShapeType = 'rect' | 'round_rect' | 'ellipse' | 'path';

export interface ShapeLayer extends BaseLayer {
  type: 'shape';
  shape: ShapeType;
  bbox: [number, number, number, number]; // [x, y, width, height]
  style: ShapeStyle;
  svg_path_d?: string;
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
  png_base64: string;
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
  points_count: number;
}

export interface LayeredVectorizeResponse {
  success: boolean;
  svg?: string;
  svg_base64?: string;
  paths?: VectorPath[];
  width?: number;
  height?: number;
  contours_count?: number;
  error?: string;
}

export interface LayeredRenderResponse {
  success: boolean;
  image_base64?: string;
  mime_type?: string;
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
