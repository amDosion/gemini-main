export interface ModelUsageSource {
  id: string;
  name?: string;
  displayName?: string;
  description?: string;
  capabilities?: {
    vision?: boolean;
    search?: boolean;
    reasoning?: boolean;
    coding?: boolean;
  };
}

export const getModelUsage = (model: ModelUsageSource): string => {
  const id = model.id.toLowerCase();
  const name = (model.displayName || model.name || '').toLowerCase();
  const description = (model.description || '').toLowerCase();
  const combined = `${id} ${name} ${description}`;

  if (combined.includes('veo') || combined.includes('video')) return '视频生成';
  if (combined.includes('upscale')) return '图片放大';
  if (combined.includes('segmentation')) return '图像分割';
  if (combined.includes('try-on') || combined.includes('tryon')) return '虚拟试衣';
  if (combined.includes('recontext') || combined.includes('product')) return '产品换景';
  if (combined.includes('embedding') || combined.includes('embed')) return '向量检索';
  if (combined.includes('tts') || combined.includes('audio') || combined.includes('speech')) return '音频生成';
  if (combined.includes('imagen') && combined.includes('generate')) return '图片生成';
  if (
    combined.includes('imagen') &&
    (combined.includes('capability') || combined.includes('edit') || combined.includes('inpaint') || combined.includes('ingredient'))
  ) {
    return '图片编辑';
  }
  if (combined.includes('gemini') && combined.includes('image')) return '图片生成 / 编辑';
  if (combined.includes('gemini')) {
    if (model.capabilities?.reasoning && model.capabilities?.search) return '对话 / 推理 / 检索';
    if (model.capabilities?.vision) return '对话 / 多模态';
    return '对话';
  }
  if (model.capabilities?.coding) return '代码生成';
  if (model.capabilities?.reasoning) return '推理';
  if (model.capabilities?.search) return '联网检索';
  if (model.capabilities?.vision) return '多模态理解';
  return '通用模型';
};
