import React from 'react';
import type { AdkExportPrecheckIssue } from './adkSessionService';

interface AdkExportPanelProps {
  issues: AdkExportPrecheckIssue[];
  emptyText?: string;
}

const getIssueBadge = (code: AdkExportPrecheckIssue['code']): string => {
  if (code === 'sensitive_fields') return '敏感字段';
  if (code === 'tenant_mismatch') return '租户不匹配';
  return '校验失败';
};

export const AdkExportPanel: React.FC<AdkExportPanelProps> = ({
  issues,
  emptyText = '暂无导出前校验失败记录。',
}) => {
  return (
    <div className="p-3 rounded border border-slate-800 bg-slate-900/40">
      <div className="text-xs text-slate-300 font-medium mb-2">导出前安全校验（precheck）</div>
      {issues.length === 0 ? (
        <div className="text-[11px] text-slate-500">{emptyText}</div>
      ) : (
        <div className="space-y-2">
          {issues.map((issue) => (
            <div key={issue.id} className="rounded border border-red-500/25 bg-red-500/10 p-2 text-[11px] text-red-100 space-y-1">
              <div className="flex items-center justify-between gap-2">
                <div className="font-medium">{issue.title}</div>
                <span className="inline-flex items-center rounded border border-red-400/30 px-1.5 py-0.5 text-[10px] text-red-200">
                  {getIssueBadge(issue.code)}
                </span>
              </div>
              <div>{issue.detail}</div>
              {issue.fields.length > 0 && (
                <div>
                  字段: {issue.fields.join(', ')}
                </div>
              )}
              {(issue.tenantId || issue.expectedTenantId) && (
                <div>
                  租户: {issue.tenantId || '-'} / 期望: {issue.expectedTenantId || '-'}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default AdkExportPanel;
