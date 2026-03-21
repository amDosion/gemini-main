/**
 * Persona 分类列表
 * 用于 UI 分类显示和选择
 */
export const PERSONA_CATEGORIES = [
  'General',
  'Image Generation',
  'Coding & Tech',
  'Creative & Writing',
  'Data & Analysis',
  'Roleplay',
  'Utility'
] as const;

export type PersonaCategory = typeof PERSONA_CATEGORIES[number];
