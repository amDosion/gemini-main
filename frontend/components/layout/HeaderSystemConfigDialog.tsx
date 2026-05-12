/**
 * Header 管理员系统配置 / 运行状态 Dialog。
 *
 * 1:1 抽离自 `Header.tsx` L849-1130 isSystemConfigDialogOpen portal block。
 */

import React from 'react';
import { createPortal } from 'react-dom';
import { Activity, Cpu, HardDrive, Loader2, Network, RefreshCw, Trash2, X } from 'lucide-react';
import type { SystemConfigPayload, SystemStatusPayload } from '../../services/systemAdmin';
import { formatBytes, formatPercent } from './headerHelpers';

type SystemConfigValueMap = Record<string, string | number | boolean | null>;

export interface HeaderSystemConfigDialogProps {
  isOpen: boolean;
  systemConfig: SystemConfigPayload | null;
  editedSystemConfig: SystemConfigValueMap;
  isLoadingSystemConfig: boolean;
  isSavingSystemConfig: boolean;
  systemConfigError: string;
  systemStatus: SystemStatusPayload | null;
  isLoadingSystemStatus: boolean;
  systemStatusError: string;
  isCleaningUp: boolean;
  hasSystemConfigChanges: boolean;
  closeSystemConfigDialog: () => void;
  handleSystemConfigValueChange: (
    key: string,
    type: 'boolean' | 'number' | 'string',
    value: string | number | boolean
  ) => void;
  loadSystemStatus: (silent?: boolean) => void | Promise<void>;
  setIsCleanupConfirmOpen: React.Dispatch<React.SetStateAction<boolean>>;
  handleSaveSystemConfig: () => void | Promise<void>;
}

export const HeaderSystemConfigDialog: React.FC<HeaderSystemConfigDialogProps> = ({
  isOpen,
  systemConfig,
  editedSystemConfig,
  isLoadingSystemConfig,
  isSavingSystemConfig,
  systemConfigError,
  systemStatus,
  isLoadingSystemStatus,
  systemStatusError,
  isCleaningUp,
  hasSystemConfigChanges,
  closeSystemConfigDialog,
  handleSystemConfigValueChange,
  loadSystemStatus,
  setIsCleanupConfirmOpen,
  handleSaveSystemConfig,
}) => {
  if (!isOpen || typeof document === 'undefined') return null;
  const configFields = systemConfig?.fields || [];
  return createPortal(
    <>
      <div className="fixed inset-0 z-[170] bg-black/60" onClick={closeSystemConfigDialog} />
      <div className="fixed inset-0 z-[171] flex items-center justify-center p-4">
        <div className="w-full max-w-5xl max-h-[90vh] bg-slate-900 border border-slate-700 rounded-xl shadow-2xl ring-1 ring-black/50 flex flex-col overflow-hidden">
          <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800">
            <div>
              <h3 className="text-base font-semibold text-white">系统配置</h3>
              <p className="text-xs text-slate-400 mt-0.5">仅管理员可见，保存后立即生效</p>
            </div>
            <button
              type="button"
              onClick={closeSystemConfigDialog}
              className="p-1 text-slate-400 hover:text-white hover:bg-slate-800 rounded-lg transition-colors"
              disabled={isSavingSystemConfig}
            >
              <X size={16} />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-5 grid grid-cols-1 lg:grid-cols-2 gap-5">
            <section className="space-y-4">
              <h4 className="text-sm font-semibold text-white">常用配置</h4>

              {isLoadingSystemConfig ? (
                <div className="h-36 flex items-center justify-center text-slate-400 text-sm">
                  <Loader2 size={16} className="animate-spin mr-2" />
                  加载系统配置...
                </div>
              ) : (
                <div className="space-y-3">
                  {configFields.map((field) => {
                    const value = editedSystemConfig[field.key];
                    if (field.type === 'boolean') {
                      return (
                        <label
                          key={field.key}
                          className="flex items-center justify-between p-3 rounded-lg border border-slate-800 bg-slate-950/50"
                        >
                          <div className="pr-4">
                            <div className="text-sm text-slate-200">{field.label}</div>
                            {field.description && (
                              <div className="text-xs text-slate-500 mt-1">{field.description}</div>
                            )}
                          </div>
                          <button
                            type="button"
                            onClick={() =>
                              handleSystemConfigValueChange(field.key, 'boolean', !(value === true))
                            }
                            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                              value ? 'bg-indigo-500' : 'bg-slate-700'
                            }`}
                            aria-pressed={value === true}
                            disabled={field.editable === false}
                          >
                            <span
                              className={`inline-block h-5 w-5 transform rounded-full bg-white transition-transform ${
                                value ? 'translate-x-5' : 'translate-x-1'
                              }`}
                            />
                          </button>
                        </label>
                      );
                    }

                    return (
                      <div
                        key={field.key}
                        className="p-3 rounded-lg border border-slate-800 bg-slate-950/50 space-y-2"
                      >
                        <div>
                          <div className="text-sm text-slate-200">{field.label}</div>
                          {field.description && (
                            <div className="text-xs text-slate-500 mt-1">{field.description}</div>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          <input
                            type={field.type === 'number' ? 'number' : 'text'}
                            value={value === null || value === undefined ? '' : String(value)}
                            min={field.min}
                            max={field.max}
                            step={field.step || 1}
                            onChange={(e) =>
                              handleSystemConfigValueChange(field.key, field.type, e.target.value)
                            }
                            className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-sm text-white focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                            disabled={field.editable === false}
                          />
                          {field.unit && (
                            <span className="text-xs text-slate-500 whitespace-nowrap">
                              {field.unit}
                            </span>
                          )}
                        </div>
                      </div>
                    );
                  })}

                  {configFields.length === 0 && (
                    <div className="text-sm text-slate-500">暂无可配置字段</div>
                  )}
                </div>
              )}

              {systemConfigError && (
                <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                  {systemConfigError}
                </div>
              )}
            </section>

            <section className="space-y-4">
              <div className="flex items-center justify-between">
                <h4 className="text-sm font-semibold text-white">系统运行状态</h4>
                <button
                  type="button"
                  onClick={() => loadSystemStatus()}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-lg text-slate-300 hover:text-white hover:bg-slate-800 transition-colors"
                >
                  <RefreshCw size={13} />
                  刷新
                </button>
                <button
                  type="button"
                  onClick={() => setIsCleanupConfirmOpen(true)}
                  disabled={isCleaningUp}
                  className="inline-flex items-center gap-1.5 px-2.5 py-1.5 text-xs rounded-lg text-red-400 hover:text-red-300 hover:bg-red-500/10 border border-red-500/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isCleaningUp ? (
                    <Loader2 size={13} className="animate-spin" />
                  ) : (
                    <Trash2 size={13} />
                  )}
                  {isCleaningUp ? '清理中...' : '清理垃圾'}
                </button>
              </div>

              {isLoadingSystemStatus ? (
                <div className="h-36 flex items-center justify-center text-slate-400 text-sm">
                  <Loader2 size={16} className="animate-spin mr-2" />
                  加载系统状态...
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div className="p-3 rounded-lg border border-slate-800 bg-slate-950/50">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs text-slate-400 inline-flex items-center gap-1.5">
                          <Activity size={13} /> CPU
                        </span>
                        <span className="text-sm text-white">
                          {formatPercent(systemStatus?.metrics.cpu.usagePercent)}
                        </span>
                      </div>
                      <div className="h-1.5 rounded bg-slate-800 overflow-hidden">
                        <div
                          className="h-full bg-indigo-500 transition-all"
                          style={{
                            width: `${Math.max(0, Math.min(100, systemStatus?.metrics.cpu.usagePercent || 0))}%`,
                          }}
                        />
                      </div>
                    </div>

                    <div className="p-3 rounded-lg border border-slate-800 bg-slate-950/50">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs text-slate-400 inline-flex items-center gap-1.5">
                          <Cpu size={13} /> 内存
                        </span>
                        <span className="text-sm text-white">
                          {formatPercent(systemStatus?.metrics.memory.usagePercent)}
                        </span>
                      </div>
                      <div className="text-xs text-slate-500">
                        {formatBytes(systemStatus?.metrics.memory.usedBytes)} /{' '}
                        {formatBytes(systemStatus?.metrics.memory.totalBytes)}
                      </div>
                    </div>

                    <div className="p-3 rounded-lg border border-slate-800 bg-slate-950/50">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs text-slate-400 inline-flex items-center gap-1.5">
                          <HardDrive size={13} /> 磁盘
                        </span>
                        <span className="text-sm text-white">
                          {formatPercent(systemStatus?.metrics.disk.usagePercent)}
                        </span>
                      </div>
                      <div className="text-xs text-slate-500">
                        {formatBytes(systemStatus?.metrics.disk.usedBytes)} /{' '}
                        {formatBytes(systemStatus?.metrics.disk.totalBytes)}
                      </div>
                      <div className="text-xs text-slate-500 mt-1">
                        R {formatBytes(systemStatus?.metrics.disk.readRateBps ?? undefined)}/s · W{' '}
                        {formatBytes(systemStatus?.metrics.disk.writeRateBps ?? undefined)}/s
                      </div>
                    </div>

                    <div className="p-3 rounded-lg border border-slate-800 bg-slate-950/50">
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-xs text-slate-400 inline-flex items-center gap-1.5">
                          <Network size={13} /> 网络
                        </span>
                        <span className="text-sm text-white">
                          {formatPercent(systemStatus?.metrics.network.usagePercent)}
                        </span>
                      </div>
                      <div className="text-xs text-slate-500">
                        ↑ {formatBytes(systemStatus?.metrics.network.txRateBps ?? undefined)}/s · ↓{' '}
                        {formatBytes(systemStatus?.metrics.network.rxRateBps ?? undefined)}/s
                      </div>
                    </div>
                  </div>

                  <div className="p-3 rounded-lg border border-slate-800 bg-slate-950/50 text-xs text-slate-500 space-y-1">
                    <div>主机: {systemStatus?.host.hostname || '—'}</div>
                    <div>平台: {systemStatus?.host.platform || '—'}</div>
                    <div>CPU 核数: {systemStatus?.host.cpuCount ?? '—'}</div>
                    <div>服务运行时长: {systemStatus?.host.processUptimeSeconds ?? 0}s</div>
                    <div>指标采集器: {systemStatus?.collector || '—'}</div>
                    {systemStatus?.collector === 'fallback' && (
                      <div className="text-amber-400">
                        当前为降级采集，内存/网络/磁盘速率需要安装 psutil
                      </div>
                    )}
                  </div>
                </div>
              )}

              {systemStatusError && (
                <div className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
                  {systemStatusError}
                </div>
              )}
            </section>
          </div>

          <div className="px-5 py-4 border-t border-slate-800 flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={closeSystemConfigDialog}
              className="px-4 py-2 text-sm rounded-lg text-slate-300 hover:bg-slate-800 transition-colors"
              disabled={isSavingSystemConfig}
            >
              关闭
            </button>
            <button
              type="button"
              onClick={handleSaveSystemConfig}
              className="px-4 py-2 text-sm rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white transition-colors disabled:opacity-60 disabled:cursor-not-allowed inline-flex items-center gap-2"
              disabled={!hasSystemConfigChanges || isSavingSystemConfig || isLoadingSystemConfig}
            >
              {isSavingSystemConfig && <Loader2 size={14} className="animate-spin" />}
              保存配置
            </button>
          </div>
        </div>
      </div>
    </>,
    document.body
  );
};
