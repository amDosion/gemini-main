import apiClient from './apiClient';
import { authService } from './auth';

export type SystemConfigFieldType = 'boolean' | 'number' | 'string';

export interface SystemConfigField {
  key: string;
  label: string;
  type: SystemConfigFieldType;
  description?: string;
  editable?: boolean;
  min?: number;
  max?: number;
  step?: number;
  unit?: string;
}

export interface SystemConfigPayload {
  values: Record<string, string | number | boolean | null>;
  fields: SystemConfigField[];
  updatedAt?: string;
}

export interface SystemStatusPayload {
  timestamp: string;
  collector: string;
  host: {
    hostname: string;
    platform: string;
    pythonVersion: string;
    cpuCount: number;
    processUptimeSeconds: number;
  };
  metrics: {
    cpu: {
      usagePercent: number | null;
    };
    memory: {
      usagePercent: number | null;
      usedBytes: number | null;
      totalBytes: number | null;
      availableBytes: number | null;
    };
    disk: {
      path: string;
      usagePercent: number | null;
      usedBytes: number | null;
      totalBytes: number | null;
      freeBytes: number | null;
      readBytes: number | null;
      writeBytes: number | null;
      readRateBps: number | null;
      writeRateBps: number | null;
    };
    network: {
      usagePercent: number | null;
      bytesSent: number | null;
      bytesRecv: number | null;
      txRateBps: number | null;
      rxRateBps: number | null;
      maxLinkSpeedMbps: number | null;
    };
  };
}

export type UpdateSystemConfigPayload = Record<string, string | number | boolean>;

class SystemAdminService {
  private readonly baseUrl = '/api/system/admin';

  async getConfig(): Promise<SystemConfigPayload> {
    return apiClient.get<SystemConfigPayload>(`${this.baseUrl}/config`);
  }

  async updateConfig(payload: UpdateSystemConfigPayload): Promise<SystemConfigPayload> {
    const result = await apiClient.request<SystemConfigPayload>(`${this.baseUrl}/config`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    // 注册开关变更后，清理缓存并通知其他页面静默刷新认证配置。
    authService.notifyConfigUpdated();

    return result;
  }

  async getStatus(): Promise<SystemStatusPayload> {
    return apiClient.get<SystemStatusPayload>(`${this.baseUrl}/status`);
  }
}

export const systemAdminService = new SystemAdminService();
export default systemAdminService;
