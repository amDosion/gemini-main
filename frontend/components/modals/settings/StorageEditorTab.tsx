/**
 * Cloud Storage Configuration Editor
 */

import React, { useState, useEffect } from 'react';
import { Save, X, Cloud } from 'lucide-react';
import {
  StorageConfig,
  StorageProvider,
  LskyConfig,
  AliyunOSSConfig,
} from '../../../types/storage';

interface StorageEditorTabProps {
  initialData: StorageConfig | null;
  existingConfigs: StorageConfig[];
  onSave: (config: StorageConfig) => Promise<void>;
  onClose: () => void;
}

export const StorageEditorTab: React.FC<StorageEditorTabProps> = ({
  initialData,
  existingConfigs,
  onSave,
  onClose,
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

  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (initialData) {
      setName(initialData.name);
      setProvider(initialData.provider);
      setEnabled(initialData.enabled);

      if (initialData.provider === 'lsky' && 'domain' in initialData.config) {
        const config = initialData.config as LskyConfig;
        setLskyDomain(config.domain);
        setLskyToken(config.token);
        setLskyStrategyId(config.strategyId?.toString() || '');
      } else if (initialData.provider === 'aliyun-oss' && 'bucket' in initialData.config) {
        const config = initialData.config as AliyunOSSConfig;
        setOssAccessKeyId(config.accessKeyId);
        setOssAccessKeySecret(config.accessKeySecret);
        setOssBucket(config.bucket);
        setOssEndpoint(config.endpoint);
        setOssCustomDomain(config.customDomain || '');
        setOssSecure(config.secure !== false);
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

    let config: LskyConfig | AliyunOSSConfig | {};

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
      if (
        !ossAccessKeyId.trim() ||
        !ossAccessKeySecret.trim() ||
        !ossBucket.trim() ||
        !ossEndpoint.trim()
      ) {
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
    } else {
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
    <div className="max-w-3xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <Cloud className="text-indigo-400" size={28} />
          <h2 className="text-2xl font-bold text-white">
            {initialData ? 'Edit Storage Config' : 'New Storage Config'}
          </h2>
        </div>
        <p className="text-slate-400 text-sm">Configure cloud storage services for image uploads</p>
      </div>

      {/* Form */}
      <div className="space-y-6">
        {/* Configuration Name */}
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-2">
            Configuration Name <span className="text-red-400">*</span>
          </label>
          <input
            type="text"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. My Storage"
            className="w-full px-4 py-3 bg-slate-900 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
          />
        </div>

        {/* Storage Type */}
        <div>
          <label className="block text-sm font-medium text-slate-300 mb-2">
            Storage Type <span className="text-red-400">*</span>
          </label>
          <select
            value={provider}
            onChange={(e) => setProvider(e.target.value as StorageProvider)}
            disabled={!!initialData}
            className="w-full px-4 py-3 bg-slate-900 border border-slate-700 rounded-xl text-white focus:outline-none focus:border-indigo-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <option value="lsky">Lsky Pro</option>
            <option value="aliyun-oss">Aliyun OSS</option>
            <option value="local">Local Storage</option>
          </select>
          {initialData && (
            <p className="mt-2 text-xs text-slate-500">Storage type cannot be changed after creation</p>
          )}
        </div>

        {/* Lsky Pro Configuration */}
        {provider === 'lsky' && (
          <div className="space-y-4 p-4 bg-blue-500/5 border border-blue-500/20 rounded-xl">
            <h3 className="text-sm font-semibold text-blue-400">Lsky Pro Configuration</h3>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Domain <span className="text-red-400">*</span>
              </label>
              <input
                type="url"
                value={lskyDomain}
                onChange={(e) => setLskyDomain(e.target.value)}
                placeholder="https://img.example.com"
                className="w-full px-4 py-3 bg-slate-900 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                API Token <span className="text-red-400">*</span>
              </label>
              <input
                type="password"
                value={lskyToken}
                onChange={(e) => setLskyToken(e.target.value)}
                placeholder="Enter API Token"
                className="w-full px-4 py-3 bg-slate-900 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Strategy ID (Optional)
              </label>
              <input
                type="number"
                value={lskyStrategyId}
                onChange={(e) => setLskyStrategyId(e.target.value)}
                placeholder="Leave empty for default strategy"
                className="w-full px-4 py-3 bg-slate-900 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
              />
            </div>
          </div>
        )}

        {/* Aliyun OSS Configuration */}
        {provider === 'aliyun-oss' && (
          <div className="space-y-4 p-4 bg-orange-500/5 border border-orange-500/20 rounded-xl">
            <h3 className="text-sm font-semibold text-orange-400">Aliyun OSS Configuration</h3>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Access Key ID <span className="text-red-400">*</span>
              </label>
              <input
                type="text"
                value={ossAccessKeyId}
                onChange={(e) => setOssAccessKeyId(e.target.value)}
                placeholder="LTAI..."
                className="w-full px-4 py-3 bg-slate-900 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Access Key Secret <span className="text-red-400">*</span>
              </label>
              <input
                type="password"
                value={ossAccessKeySecret}
                onChange={(e) => setOssAccessKeySecret(e.target.value)}
                placeholder="Enter Access Key Secret"
                className="w-full px-4 py-3 bg-slate-900 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Bucket Name <span className="text-red-400">*</span>
              </label>
              <input
                type="text"
                value={ossBucket}
                onChange={(e) => setOssBucket(e.target.value)}
                placeholder="my-bucket"
                className="w-full px-4 py-3 bg-slate-900 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Endpoint <span className="text-red-400">*</span>
              </label>
              <input
                type="text"
                value={ossEndpoint}
                onChange={(e) => setOssEndpoint(e.target.value)}
                placeholder="oss-cn-hangzhou.aliyuncs.com"
                className="w-full px-4 py-3 bg-slate-900 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
              />
              <p className="mt-2 text-xs text-slate-500">
                OSS Endpoint, e.g., oss-cn-hangzhou.aliyuncs.com
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">
                Custom CDN Domain (Optional)
              </label>
              <input
                type="url"
                value={ossCustomDomain}
                onChange={(e) => setOssCustomDomain(e.target.value)}
                placeholder="https://cdn.example.com"
                className="w-full px-4 py-3 bg-slate-900 border border-slate-700 rounded-xl text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500 transition-colors"
              />
              <p className="mt-2 text-xs text-slate-500">
                Used for public access URL, leave empty to use OSS default domain
              </p>
            </div>

            <div className="flex items-center gap-3">
              <input
                type="checkbox"
                id="ossSecure"
                checked={ossSecure}
                onChange={(e) => setOssSecure(e.target.checked)}
                className="w-4 h-4 rounded border-slate-700 bg-slate-900 text-indigo-600 focus:ring-indigo-500 focus:ring-offset-slate-950"
              />
              <label htmlFor="ossSecure" className="text-sm text-slate-300">
                Use HTTPS
              </label>
            </div>
          </div>
        )}

        {/* Enabled Status */}
        <div className="flex items-center gap-3">
          <input
            type="checkbox"
            id="enabled"
            checked={enabled}
            onChange={(e) => setEnabled(e.target.checked)}
            className="w-4 h-4 rounded border-slate-700 bg-slate-900 text-indigo-600 focus:ring-indigo-500 focus:ring-offset-slate-950"
          />
          <label htmlFor="enabled" className="text-sm text-slate-300">
            Enable this configuration
          </label>
        </div>

        {/* Error Message */}
        {error && (
          <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-red-400 text-sm">
            {error}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="mt-8 pt-6 border-t border-slate-800 flex justify-end gap-3">
        <button
          onClick={onClose}
          disabled={isSaving}
          className="px-5 py-2.5 rounded-xl text-slate-400 hover:text-white hover:bg-slate-800 transition-colors text-sm font-medium disabled:opacity-50"
        >
          <X size={16} className="inline mr-2" />
          Cancel
        </button>
        <button
          onClick={handleSave}
          disabled={isSaving}
          className="px-5 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl font-medium transition-colors text-sm shadow-lg shadow-indigo-900/20 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Save size={16} className="inline mr-2" />
          {isSaving ? 'Saving...' : 'Save Configuration'}
        </button>
      </div>
    </div>
  );
};
