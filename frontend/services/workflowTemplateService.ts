/**
 * Workflow Template Service - 工作流模板服务
 * 
 * 提供工作流模板的 CRUD 操作
 */

export interface WorkflowTemplate {
  id: string;
  userId: string;
  name: string;
  description?: string;
  category: string;  // image-edit, excel-analysis, general等
  workflowType: string;  // sequential, parallel, coordinator
  config: {
    nodes: any[];
    edges: any[];
    [key: string]: any;
  };
  isPublic: boolean;
  version: number;
  createdAt: number;
  updatedAt: number;
}

export interface CreateWorkflowTemplateRequest {
  name: string;
  description?: string;
  category: string;
  workflowType: string;
  config: {
    nodes: any[];
    edges: any[];
    [key: string]: any;
  };
  isPublic?: boolean;
}

export interface UpdateWorkflowTemplateRequest {
  name?: string;
  description?: string;
  category?: string;
  workflowType?: string;
  config?: {
    nodes: any[];
    edges: any[];
    [key: string]: any;
  };
  isPublic?: boolean;
}

class WorkflowTemplateService {
  private baseUrl = '/api/multi-agent/workflows/templates';

  private getHeaders(): HeadersInit {
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    };
    // 尝试多种方式获取 token
    let token = localStorage.getItem('access_token');
    if (!token) {
      // 尝试从 Cookie 获取（向后兼容）
      const cookies = document.cookie.split(';');
      for (const cookie of cookies) {
        const [name, value] = cookie.trim().split('=');
        if (name === 'access_token') {
          token = value;
          break;
        }
      }
    }
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
      console.log('[WorkflowTemplateService] Using token for authentication');
    } else {
      console.warn('[WorkflowTemplateService] No token found, request may fail');
    }
    return headers;
  }

  /**
   * 创建工作流模板
   */
  async createTemplate(request: CreateWorkflowTemplateRequest): Promise<WorkflowTemplate> {
    const response = await fetch(this.baseUrl, {
      method: 'POST',
      headers: this.getHeaders(),
      credentials: 'include',
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to create workflow template');
    }

    return response.json();
  }

  /**
   * 获取工作流模板列表
   */
  async listTemplates(options?: {
    category?: string;
    workflowType?: string;
    search?: string;
    includePublic?: boolean;
  }): Promise<WorkflowTemplate[]> {
    const params = new URLSearchParams();
    // ✅ Query 参数使用 camelCase（中间件自动转换为 snake_case）
    if (options?.category) params.append('category', options.category);
    if (options?.workflowType) params.append('workflowType', options.workflowType);
    if (options?.search) params.append('search', options.search);
    if (options?.includePublic !== undefined) params.append('includePublic', String(options.includePublic));

    const url = params.toString() ? `${this.baseUrl}?${params.toString()}` : this.baseUrl;
    console.log('[WorkflowTemplateService] Fetching templates from:', url);
    
    const response = await fetch(url, {
      headers: this.getHeaders(),
      credentials: 'include'
    });

    console.log('[WorkflowTemplateService] Response status:', response.status, response.statusText);

    if (!response.ok) {
      let errorDetail = 'Failed to list workflow templates';
      try {
        const error = await response.json();
        errorDetail = error.detail || error.message || errorDetail;
        console.error('[WorkflowTemplateService] Error response:', error);
      } catch (e) {
        console.error('[WorkflowTemplateService] Failed to parse error response:', e);
        errorDetail = `HTTP ${response.status}: ${response.statusText}`;
      }
      throw new Error(errorDetail);
    }

    const data = await response.json();
    return data.templates || [];
  }

  /**
   * 获取单个工作流模板
   */
  async getTemplate(templateId: string): Promise<WorkflowTemplate> {
    const response = await fetch(`${this.baseUrl}/${templateId}`, {
      headers: this.getHeaders(),
      credentials: 'include'
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to get workflow template');
    }

    return response.json();
  }

  /**
   * 更新工作流模板
   */
  async updateTemplate(
    templateId: string,
    request: UpdateWorkflowTemplateRequest
  ): Promise<WorkflowTemplate> {
    const response = await fetch(`${this.baseUrl}/${templateId}`, {
      method: 'PUT',
      headers: this.getHeaders(),
      credentials: 'include',
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to update workflow template');
    }

    return response.json();
  }

  /**
   * 删除工作流模板
   */
  async deleteTemplate(templateId: string): Promise<void> {
    const response = await fetch(`${this.baseUrl}/${templateId}`, {
      method: 'DELETE',
      headers: this.getHeaders(),
      credentials: 'include'
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to delete workflow template');
    }
  }

  /**
   * 列出可用的 ADK samples 模板
   */
  async listADKSamplesTemplates(): Promise<Array<{
    id: string;
    name: string;
    description: string;
    category: string;
    workflowType: string;
    path: string;
    source: string;
  }>> {
    const response = await fetch('/api/multi-agent/workflows/adk-samples/templates', {
      headers: this.getHeaders(),
      credentials: 'include'
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to list ADK samples templates');
    }

    const data = await response.json();
    return data.templates || [];
  }

  /**
   * 从 ADK samples 导入模板
   */
  async importADKSampleTemplate(
    templateId: string,
    customName?: string,
    isPublic: boolean = false
  ): Promise<WorkflowTemplate> {
    const response = await fetch('/api/multi-agent/workflows/adk-samples/import', {
      method: 'POST',
      headers: this.getHeaders(),
      credentials: 'include',
      body: JSON.stringify({
        templateId: templateId,
        customName: customName,
        isPublic: isPublic
      })
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to import ADK samples template');
    }

    return response.json();
  }

  /**
   * 导入所有 ADK samples 模板
   */
  async importAllADKSamplesTemplates(isPublic: boolean = false): Promise<WorkflowTemplate[]> {
    const params = new URLSearchParams();
    // ✅ Query 参数使用 camelCase（中间件自动转换为 snake_case）
    params.append('isPublic', String(isPublic));
    
    const response = await fetch(`/api/multi-agent/workflows/adk-samples/import-all?${params.toString()}`, {
      method: 'POST',
      headers: this.getHeaders(),
      credentials: 'include'
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to import all ADK samples templates');
    }

    const data = await response.json();
    return data.templates || [];
  }
}

export const workflowTemplateService = new WorkflowTemplateService();
