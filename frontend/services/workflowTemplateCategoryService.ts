import { apiClient } from './apiClient';

export interface WorkflowTemplateCategoryItem {
  id?: string | null;
  name: string;
  createdAt?: number | null;
  updatedAt?: number | null;
}

interface WorkflowTemplateCategoryListResponse {
  categories: WorkflowTemplateCategoryItem[];
  count: number;
}

const normalizeCategoryItem = (item: unknown): WorkflowTemplateCategoryItem => {
  const obj = (item && typeof item === 'object' ? item : {}) as Record<string, unknown>;
  return {
    id: typeof obj.id === 'string' ? obj.id : null,
    name: String(obj.name || '').trim(),
    createdAt: typeof obj.createdAt === 'number' ? obj.createdAt : null,
    updatedAt: typeof obj.updatedAt === 'number' ? obj.updatedAt : null,
  };
};

export const listWorkflowTemplateCategories = async (
  options: {
    includePublic?: boolean;
    ensureDefaults?: boolean;
  } = {}
): Promise<WorkflowTemplateCategoryItem[]> => {
  const params = new URLSearchParams({
    include_public: String(options.includePublic !== false),
    ensure_defaults: String(options.ensureDefaults !== false),
  });
  const response = await apiClient.get<WorkflowTemplateCategoryListResponse>(
    `/api/workflows/template-categories?${params.toString()}`
  );
  const categories = Array.isArray(response?.categories)
    ? response.categories.map(normalizeCategoryItem).filter((item) => item.name.length > 0)
    : [];

  const seen = new Set<string>();
  return categories.filter((item) => {
    const key = item.name.toLowerCase();
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
};

export const createWorkflowTemplateCategory = async (
  name: string
): Promise<WorkflowTemplateCategoryItem> => {
  const response = await apiClient.post<Record<string, unknown>>(
    '/api/workflows/template-categories',
    { name }
  );
  return normalizeCategoryItem(response);
};
