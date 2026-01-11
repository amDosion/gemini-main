/**
 * Cloud Storage Configuration Editor
 */

import React, { useState, useEffect } from 'react';
import { createPortal } from 'react-dom';
import { Save, X, Cloud, Server, HardDrive, Database } from 'lucide-react';
import {
  StorageConfig,
  StorageProvider,
  LskyConfig,
  AliyunOSSConfig,
  TencentCOSConfig,
  GoogleDriveConfig,
  S3CompatibleConfig,
} from '../../../types/storage';

interface StorageEditorTabProps {
  initialData: StorageConfig | null;
  existingConfigs: StorageConfig[];
  onSave: (config: StorageConfig) => Promise<void>;
  onClose: () => void;
  footerNode?: HTMLDivElement | null;
}

export const StorageEditorTab: React.FC<StorageEditorTabProps> = ({
  initialData,
  existingConfigs,
  onSave,
  onClose,
  footerNode
}) => {
  const [name, setName] = useState('');
  const [provider, setProvider] = useState<StorageProvider>('lsky');
  const [enabled, setEnabled] = useState(true);

  // Lsky Configuration
  const [lskyDomain, setLskyDomain] = useState('');
  const [lskyToken, setLskyToken] = useState('');
  const [lskyStrategyId, setLskyStrategyId] = useState('');

  // Aliyun OSS Configuration
  const [ossAccessKeyId, setOssAccessKeyId] = useState('');
  const [ossAccessKeySecret, setOssAccessKeySecret] = useState('');
  const [ossBucket, setOssBucket] = useState('');
  const [ossEndpoint, setOssEndpoint] = useState('oss-cn-hangzhou.aliyuncs.com');
  const [ossCustomDomain, setOssCustomDomain] = useState('');
  const [ossSecure, setOssSecure] = useState(true);

  // Tencent COS Configuration
  const [tencentSecretId, setTencentSecretId] = useState('');
  const [tencentSecretKey, setTencentSecretKey] = useState('');
  const [tencentBucket, setTencentBucket] = useState('');
  const [tencentRegion, setTencentRegion] = useState('ap-guangzhou');
  const [tencentDomain, setTencentDomain] = useState('');
  const [tencentPathPrefix, setTencentPathPrefix] = useState('');

  // Google Drive Configuration
  const [gdriveClientId, setGdriveClientId] = useState('');
  const [gdriveClientSecret, setGdriveClientSecret] = useState('');
  const [gdriveRefreshToken, setGdriveRefreshToken] = useState('');
  const [gdriveFolderId, setGdriveFolderId] = useState('');

  // S3 Compatible Configuration
  const [s3AccessKeyId, setS3AccessKeyId] = useState('');
  const [s3SecretAccessKey, setS3SecretAccessKey] = useState('');
  const [s3Endpoint, setS3Endpoint] = useState('');
  const [s3Bucket, setS3Bucket] = useState('');
  const [s3Region, setS3Region] = useState('');
  const [s3PathPrefix, setS3PathPrefix] = useState('');
  const [s3CustomDomain, setS3CustomDomain] = useState('');
  const [s3ForcePathStyle, setS3ForcePathStyle] = useState(true);

  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (initialData) {
      setName(initialData.name);
      setProvider(initialData.provider);
      setEnabled(initialData.enabled);

      if (initialData.provider === 'lsky') {
        const config = initialData.config as LskyConfig;
        setLskyDomain(config.domain);
        setLskyToken(config.token);
        setLskyStrategyId(config.strategyId?.toString() || '');
      } else if (initialData.provider === 'aliyun-oss') {
        const config = initialData.config as AliyunOSSConfig;
        setOssAccessKeyId(config.accessKeyId);
        setOssAccessKeySecret(config.accessKeySecret);
        setOssBucket(config.bucket);
        setOssEndpoint(config.endpoint);
        setOssCustomDomain(config.customDomain || '');
        setOssSecure(config.secure !== false);
      } else if (initialData.provider === 'tencent-cos') {
        const config = initialData.config as TencentCOSConfig;
        setTencentSecretId(config.secretId);
        setTencentSecretKey(config.secretKey);
        setTencentBucket(config.bucket);
        setTencentRegion(config.region);
        setTencentDomain(config.domain || '');
        setTencentPathPrefix(config.pathPrefix || '');
      } else if (initialData.provider === 'google-drive') {
        const config = initialData.config as GoogleDriveConfig;
        setGdriveClientId(config.clientId);
        setGdriveClientSecret(config.clientSecret);
        setGdriveRefreshToken(config.refreshToken);
        setGdriveFolderId(config.folderId || '');
      } else if (initialData.provider === 's3-compatible') {
        const config = initialData.config as S3CompatibleConfig;
        setS3AccessKeyId(config.accessKeyId);
        setS3SecretAccessKey(config.secretAccessKey);
        setS3Endpoint(config.endpoint);
        setS3Bucket(config.bucket);
        setS3Region(config.region || '');
        setS3PathPrefix(config.pathPrefix || '');
        setS3CustomDomain(config.customDomain || '');
        setS3ForcePathStyle(config.forcePathStyle);
      }
    }
  }, [initialData]);

  const handleSave = async () => {
    setError('');

    // Validation
    if (!name.trim()) {
      setError('Please enter configuration name');
      return;
    }

    // Check for duplicate configuration names
    const trimmedName = name.trim();
    const isDuplicate = existingConfigs.some(
      config => config.name === trimmedName && config.id !== initialData?.id
    );
    
    if (isDuplicate) {
      setError(`Configuration name "${trimmedName}" already exists. Please use a different name.`);
      return;
    }

    let config: any = {};

    if (provider === 'lsky') {
      if (!lskyDomain.trim() || !lskyToken.trim()) {
        setError('Please enter Lsky Pro Domain and Token');
        return;
      }
      config = {
        domain: lskyDomain.trim(),
        token: lskyToken.trim(),
        strategyId: lskyStrategyId ? parseInt(lskyStrategyId) : undefined,
      };
    } else if (provider === 'aliyun-oss') {
      if (!ossAccessKeyId.trim() || !ossAccessKeySecret.trim() || !ossBucket.trim() || !ossEndpoint.trim()) {
        setError('Please fill in required fields for Aliyun OSS');
        return;
      }
      config = {
        accessKeyId: ossAccessKeyId.trim(),
        accessKeySecret: ossAccessKeySecret.trim(),
        bucket: ossBucket.trim(),
        endpoint: ossEndpoint.trim(),
        customDomain: ossCustomDomain.trim() || undefined,
        secure: ossSecure,
      };
    } else if (provider === 'tencent-cos') {
      if (!tencentSecretId.trim() || !tencentSecretKey.trim() || !tencentBucket.trim() || !tencentRegion.trim()) {
        setError('Please fill in required fields for Tencent COS');
        return;
      }
      config = {
        secretId: tencentSecretId.trim(),
        secretKey: tencentSecretKey.trim(),
        bucket: tencentBucket.trim(),
        region: tencentRegion.trim(),
        domain: tencentDomain.trim() || undefined,
        pathPrefix: tencentPathPrefix.trim() || undefined,
      };
    } else if (provider === 'google-drive') {
      if (!gdriveClientId.trim() || !gdriveClientSecret.trim() || !gdriveRefreshToken.trim()) {
        setError('Please fill in required fields for Google Drive');
        return;
      }
      config = {
        clientId: gdriveClientId.trim(),
        clientSecret: gdriveClientSecret.trim(),
        refreshToken: gdriveRefreshToken.trim(),
        folderId: gdriveFolderId.trim() || undefined,
      };
    } else if (provider === 's3-compatible') {
      if (!s3AccessKeyId.trim() || !s3SecretAccessKey.trim() || !s3Endpoint.trim() || !s3Bucket.trim()) {
        setError('Please fill in required fields for S3 Compatible Storage');
        return;
      }
      config = {
        accessKeyId: s3AccessKeyId.trim(),
        secretAccessKey: s3SecretAccessKey.trim(),
        endpoint: s3Endpoint.trim(),
        bucket: s3Bucket.trim(),
        region: s3Region.trim() || undefined,
        pathPrefix: s3PathPrefix.trim() || undefined,
        customDomain: s3CustomDomain.trim() || undefined,
        forcePathStyle: s3ForcePathStyle,
      };
    } else if (provider === 'local') {
      config = {};
    }

    const storageConfig: StorageConfig = {
      id: initialData?.id || `storage_${Date.now()}`,
      name: name.trim(),
      provider,
      enabled,
      config,
      createdAt: initialData?.createdAt || Date.now(),
      updatedAt: Date.now(),
    };

    setIsSaving(true);
    try {
      await onSave(storageConfig);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Save failed');
      setIsSaving(false);
    }
  };

  return (
    <>
      <div className="absolute inset-0 flex flex-col p-3 md:p-6 space-y-4 md:space-y-6">
        {/* Header */}
        <div className="shrink-0 border-b border-slate-800 pb-3 md:pb-4">
          <div className="flex items-center gap-2 md:gap-3 mb-1">
            <Cloud className="text-indigo-400" size={24} />
            <h2 className="text-lg md:text-2xl font-bold text-white">
              {initialData ? 'Edit Storage Config' : 'New Storage Config'}
            </h2>
          </div>
          <p className="text-slate-400 text-xs md:text-sm">Configure cloud storage services for image uploads</p>
        </div>

        {/* Form Container */}
        <div className="flex-1 overflow-y-auto min-h-0 custom-scrollbar pr-1 pb-4 md:pb-4">
          <div className="space-y-4 md:space-y-6">
            {/* Configuration Name */}
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">
                Configuration Name <span className="text-red-400">*</span>
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. My Storage"
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors text-sm"
              />
            </div>

            {/* Storage Type */}
            <div>
              <label className="block text-xs font-medium text-slate-300 mb-1.5">
                Storage Type <span className="text-red-400">*</span>
              </label>
              <select
                value={provider}
                onChange={(e) => setProvider(e.target.value as StorageProvider)}
                disabled={!!initialData}
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-white focus:outline-none focus:border-indigo-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed text-sm appearance-none"
              >
                <option value="lsky">Lsky Pro</option>
                <option value="aliyun-oss">Aliyun OSS</option>
                <option value="tencent-cos">Tencent COS</option>
                <option value="google-drive">Google Drive</option>
                <option value="s3-compatible">S3 Compatible</option>
                <option value="local">Local Storage</option>
              </select>
              {initialData && (
                <p className="mt-1 text-[10px] text-slate-500">Storage type cannot be changed after creation</p>
              )}
            </div>

            {/* Lsky Pro Configuration */}
            {provider === 'lsky' && (
              <div className="space-y-3 md:space-y-4 p-3 md:p-4 bg-slate-900/30 border border-slate-800/50 rounded-xl">
                <h3 className="text-xs md:text-sm font-semibold text-blue-400 uppercase tracking-widest flex items-center gap-2">
                  <Cloud size={14} /> Lsky Pro Configuration
                </h3>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1.5">
                    Domain <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="url"
                    value={lskyDomain}
                    onChange={(e) => setLskyDomain(e.target.value)}
                    placeholder="https://img.example.com"
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors text-xs font-mono"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1.5">
                    API Token <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="password"
                    value={lskyToken}
                    onChange={(e) => setLskyToken(e.target.value)}
                    placeholder="Enter API Token"
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors text-xs font-mono"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1.5">
                    Strategy ID (Optional)
                  </label>
                  <input
                    type="number"
                    value={lskyStrategyId}
                    onChange={(e) => setLskyStrategyId(e.target.value)}
                    placeholder="Leave empty for default strategy"
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors text-xs font-mono"
                  />
                </div>
              </div>
            )}

            {/* Aliyun OSS Configuration */}
            {provider === 'aliyun-oss' && (
              <div className="space-y-3 md:space-y-4 p-3 md:p-4 bg-slate-900/30 border border-slate-800/50 rounded-xl">
                <h3 className="text-xs md:text-sm font-semibold text-orange-400 uppercase tracking-widest flex items-center gap-2">
                  <Server size={14} /> Aliyun OSS Configuration
                </h3>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1.5">
                    Access Key ID <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="text"
                    value={ossAccessKeyId}
                    onChange={(e) => setOssAccessKeyId(e.target.value)}
                    placeholder="LTAI..."
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors text-xs font-mono"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1.5">
                    Access Key Secret <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="password"
                    value={ossAccessKeySecret}
                    onChange={(e) => setOssAccessKeySecret(e.target.value)}
                    placeholder="Enter Access Key Secret"
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors text-xs font-mono"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1.5">
                    Bucket Name <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="text"
                    value={ossBucket}
                    onChange={(e) => setOssBucket(e.target.value)}
                    placeholder="my-bucket"
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors text-xs font-mono"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1.5">
                    Endpoint <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="text"
                    value={ossEndpoint}
                    onChange={(e) => setOssEndpoint(e.target.value)}
                    placeholder="oss-cn-hangzhou.aliyuncs.com"
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors text-xs font-mono"
                  />
                  <p className="mt-1 text-[10px] text-slate-500">
                    OSS Endpoint, e.g., oss-cn-hangzhou.aliyuncs.com
                  </p>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1.5">
                    Custom CDN Domain (Optional)
                  </label>
                  <input
                    type="url"
                    value={ossCustomDomain}
                    onChange={(e) => setOssCustomDomain(e.target.value)}
                    placeholder="https://cdn.example.com"
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors text-xs font-mono"
                  />
                </div>

                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="ossSecure"
                    checked={ossSecure}
                    onChange={(e) => setOssSecure(e.target.checked)}
                    className="w-3.5 h-3.5 rounded border-slate-700 bg-slate-900 text-indigo-600 focus:ring-indigo-500 focus:ring-offset-slate-950"
                  />
                  <label htmlFor="ossSecure" className="text-xs text-slate-300">
                    Use HTTPS
                  </label>
                </div>
              </div>
            )}

            {/* Tencent COS Configuration */}
            {provider === 'tencent-cos' && (
              <div className="space-y-3 md:space-y-4 p-3 md:p-4 bg-slate-900/30 border border-slate-800/50 rounded-xl">
                <h3 className="text-xs md:text-sm font-semibold text-green-400 uppercase tracking-widest flex items-center gap-2">
                  <Server size={14} /> Tencent COS Configuration
                </h3>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1.5">
                    SecretId <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="text"
                    value={tencentSecretId}
                    onChange={(e) => setTencentSecretId(e.target.value)}
                    placeholder="AKID..."
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors text-xs font-mono"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1.5">
                    SecretKey <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="password"
                    value={tencentSecretKey}
                    onChange={(e) => setTencentSecretKey(e.target.value)}
                    placeholder="Enter SecretKey"
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors text-xs font-mono"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1.5">
                    Bucket Name <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="text"
                    value={tencentBucket}
                    onChange={(e) => setTencentBucket(e.target.value)}
                    placeholder="bucket-1250000000"
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors text-xs font-mono"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1.5">
                    Region <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="text"
                    value={tencentRegion}
                    onChange={(e) => setTencentRegion(e.target.value)}
                    placeholder="ap-guangzhou"
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors text-xs font-mono"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1.5">
                    Custom Domain (Optional)
                  </label>
                  <input
                    type="text"
                    value={tencentDomain}
                    onChange={(e) => setTencentDomain(e.target.value)}
                    placeholder="https://cdn.example.com"
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors text-xs font-mono"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1.5">
                    Path Prefix (Optional)
                  </label>
                  <input
                    type="text"
                    value={tencentPathPrefix}
                    onChange={(e) => setTencentPathPrefix(e.target.value)}
                    placeholder="e.g. uploads/"
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors text-xs font-mono"
                  />
                </div>
              </div>
            )}

            {/* Google Drive Configuration */}
            {provider === 'google-drive' && (
              <div className="space-y-3 md:space-y-4 p-3 md:p-4 bg-slate-900/30 border border-slate-800/50 rounded-xl">
                <h3 className="text-xs md:text-sm font-semibold text-yellow-400 uppercase tracking-widest flex items-center gap-2">
                  <HardDrive size={14} /> Google Drive Configuration
                </h3>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1.5">
                    Client ID <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="text"
                    value={gdriveClientId}
                    onChange={(e) => setGdriveClientId(e.target.value)}
                    placeholder="Enter Client ID"
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors text-xs font-mono"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1.5">
                    Client Secret <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="password"
                    value={gdriveClientSecret}
                    onChange={(e) => setGdriveClientSecret(e.target.value)}
                    placeholder="Enter Client Secret"
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors text-xs font-mono"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1.5">
                    Refresh Token <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="password"
                    value={gdriveRefreshToken}
                    onChange={(e) => setGdriveRefreshToken(e.target.value)}
                    placeholder="Enter Refresh Token"
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors text-xs font-mono"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1.5">
                    Folder ID (Optional)
                  </label>
                  <input
                    type="text"
                    value={gdriveFolderId}
                    onChange={(e) => setGdriveFolderId(e.target.value)}
                    placeholder="Root folder if empty"
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors text-xs font-mono"
                  />
                </div>
              </div>
            )}

            {/* S3 Compatible Configuration */}
            {provider === 's3-compatible' && (
              <div className="space-y-3 md:space-y-4 p-3 md:p-4 bg-slate-900/30 border border-slate-800/50 rounded-xl">
                <h3 className="text-xs md:text-sm font-semibold text-purple-400 uppercase tracking-widest flex items-center gap-2">
                  <Database size={14} /> S3 Compatible Configuration
                </h3>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1.5">
                    Access Key ID <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="text"
                    value={s3AccessKeyId}
                    onChange={(e) => setS3AccessKeyId(e.target.value)}
                    placeholder="Access Key ID"
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors text-xs font-mono"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1.5">
                    Secret Access Key <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="password"
                    value={s3SecretAccessKey}
                    onChange={(e) => setS3SecretAccessKey(e.target.value)}
                    placeholder="Secret Access Key"
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors text-xs font-mono"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1.5">
                    Endpoint <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="text"
                    value={s3Endpoint}
                    onChange={(e) => setS3Endpoint(e.target.value)}
                    placeholder="https://s3.example.com"
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors text-xs font-mono"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1.5">
                    Bucket Name <span className="text-red-400">*</span>
                  </label>
                  <input
                    type="text"
                    value={s3Bucket}
                    onChange={(e) => setS3Bucket(e.target.value)}
                    placeholder="my-bucket"
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors text-xs font-mono"
                  />
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-slate-300 mb-1.5">
                      Region (Optional)
                    </label>
                    <input
                      type="text"
                      value={s3Region}
                      onChange={(e) => setS3Region(e.target.value)}
                      placeholder="us-east-1"
                      className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors text-xs font-mono"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-300 mb-1.5">
                      Path Prefix (Optional)
                    </label>
                    <input
                      type="text"
                      value={s3PathPrefix}
                      onChange={(e) => setS3PathPrefix(e.target.value)}
                      placeholder="uploads/"
                      className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors text-xs font-mono"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1.5">
                    Custom Domain (Optional)
                  </label>
                  <input
                    type="text"
                    value={s3CustomDomain}
                    onChange={(e) => setS3CustomDomain(e.target.value)}
                    placeholder="https://cdn.example.com"
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors text-xs font-mono"
                  />
                </div>

                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="s3ForcePathStyle"
                    checked={s3ForcePathStyle}
                    onChange={(e) => setS3ForcePathStyle(e.target.checked)}
                    className="w-3.5 h-3.5 rounded border-slate-700 bg-slate-900 text-indigo-600 focus:ring-indigo-500 focus:ring-offset-slate-950"
                  />
                  <label htmlFor="s3ForcePathStyle" className="text-xs text-slate-300">
                    Force Path Style
                  </label>
                </div>
              </div>
            )}

            {/* Enabled Status */}
            <div className="flex items-center gap-3 pt-2">
              <input
                type="checkbox"
                id="enabled"
                checked={enabled}
                onChange={(e) => setEnabled(e.target.checked)}
                className="w-4 h-4 rounded border-slate-700 bg-slate-900 text-indigo-600 focus:ring-indigo-500 focus:ring-offset-slate-950"
              />
              <label htmlFor="enabled" className="text-xs md:text-sm text-slate-300">
                Enable this configuration
              </label>
            </div>

            {/* Error Message */}
            {error && (
              <div className="p-3 md:p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-xs md:text-sm">
                {error}
              </div>
            )}

            {/* Bottom spacer for safe scroll area */}
            <div className="h-4"></div>
          </div>
        </div>

      </div>

      {/* Footer Portal */}
      {footerNode && createPortal(
        <>
          <button
            onClick={onClose}
            disabled={isSaving}
            className="px-4 py-2 rounded-lg text-slate-400 hover:text-white hover:bg-slate-900 transition-colors text-xs font-medium disabled:opacity-50 flex items-center gap-1"
          >
            <X size={16} />
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={isSaving}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg font-medium transition-colors text-sm shadow-lg shadow-indigo-900/20 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
          >
            <Save size={16} />
            {isSaving ? 'Saving...' : 'Save'}
          </button>
        </>,
        footerNode
      )}
    </>
  );
};
