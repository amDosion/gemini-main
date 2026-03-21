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

const normalizeCategoryItem = (item: any): WorkflowTemplateCategoryItem => {
  return {
    id: typeof item?.id === 'string' ? item.id : null,
    name: String(item?.name || '').trim(),
    createdAt: typeof item?.createdAt === 'number' ? item.createdAt : null,
    updatedAt: typeof item?.updatedAt === 'number' ? item.updatedAt : null,
  };
};

export const listWorkflowTemplateCategories = async (
  options: {
    includePublic?: boolean;
    ensureDefaults?: boolean;
  } = {},
): Promise<WorkflowTemplateCategoryItem[]> => {
  const includePublic = options.includePublic !== false;
  const ensureDefaults = options.ensureDefaults !== false;
  const params = new URLSearchParams();
  params.set('include_public', includePublic ? 'true' : 'false');
  params.set('ensure_defaults', ensureDefaults ? 'true' : 'false');
  const response = await apiClient.get<WorkflowTemplateCategoryListResponse>(
    `/api/workflows/template-categories?${params.toString()}`,
  );
  const categories = Array.isArray(response?.categories)
    ? response.categories.map(normalizeCategoryItem).filter((item) => item.name.length > 0)
    : [];

  const deduped: WorkflowTemplateCategoryItem[] = [];
  const seen = new Set<string>();
  categories.forEach((item) => {
    const key = item.name.toLowerCase();
    if (seen.has(key)) return;
    seen.add(key);
    deduped.push(item);
  });
  return deduped;
};

export const createWorkflowTemplateCategory = async (
  name: string,
): Promise<WorkflowTemplateCategoryItem> => {
  const response = await apiClient.post<any>(
    '/api/workflows/template-categories',
    { name },
  );
  return normalizeCategoryItem(response);
};

