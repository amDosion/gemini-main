/**
 * 云存储配置类型定义
 */

import { ReactNode } from "react";

export type StorageProvider = 'lsky' | 'aliyun-oss' | 'local' | 'tencent-cos' | 'google-drive' | 's3-compatible';

export interface StorageConfig {
  id: string;
  name: string;
  provider: StorageProvider;
  enabled: boolean;
  config: LskyConfig | AliyunOSSConfig | LocalConfig | TencentCOSConfig | GoogleDriveConfig | S3CompatibleConfig;
  createdAt: number;
  updatedAt: number;
}

/**
 * 兰空图床配置
 */
export interface LskyConfig {
  domain: string;  // 例如：https://img.example.com
  token: string;   // API Token
  strategyId?: number;  // 存储策略 ID（可选）
}

/**
 * 阿里云 OSS 配置
 */
export interface AliyunOSSConfig {
  [x: string]: ReactNode;
  accessKeyId: string;        // Access Key ID
  accessKeySecret: string;    // Access Key Secret
  bucket: string;             // Bucket 名称
  endpoint: string;           // OSS 访问端点，例如：oss-cn-hangzhou.aliyuncs.com 或自定义域名
  customDomain?: string;      // 自定义 CDN 域名（可选），用于生成公开访问 URL
  secure?: boolean;           // 是否使用 HTTPS（默认 true）
}

/**
 * 本地存储配置
 */
export interface LocalConfig {
  // 本地存储不需要额外配置
}

/**
 * 腾讯云 COS 配置
 */
export interface TencentCOSConfig {
  secretId: string;
  secretKey: string;
  bucket: string;
  region: string;
  domain?: string;
  pathPrefix?: string;
}

/**
 * Google Drive 配置
 */
export interface GoogleDriveConfig {
  clientId: string;
  clientSecret: string;
  refreshToken: string;
  folderId?: string;
}

/**
 * S3 兼容存储配置
 */
export interface S3CompatibleConfig {
  accessKeyId: string;
  secretAccessKey: string;
  endpoint: string;
  bucket: string;
  region?: string;
  pathPrefix?: string;
  customDomain?: string;
  forcePathStyle: boolean;
}

/**
 * 存储上传结果
 */
export interface StorageUploadResult {
  success: boolean;
  url?: string;
  error?: string;
  provider?: StorageProvider;
}
