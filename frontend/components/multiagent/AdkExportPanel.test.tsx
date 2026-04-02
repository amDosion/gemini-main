// @vitest-environment jsdom
import React from 'react';
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';

import { AdkExportPanel } from './AdkExportPanel';
import type { AdkExportPrecheckIssue } from './adkSessionService';

describe('AdkExportPanel', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders sensitive-field and tenant-mismatch precheck failures', () => {
    const issues: AdkExportPrecheckIssue[] = [
      {
        id: 'issue-1',
        code: 'sensitive_fields',
        title: '导出前校验失败：命中敏感字段',
        detail: '检测到敏感字段，导出被拒绝。',
        fields: ['phone', 'id_card'],
        tenantId: '',
        expectedTenantId: '',
        sourcePath: 'snapshot.export_precheck.issues[0]',
        raw: {},
      },
      {
        id: 'issue-2',
        code: 'tenant_mismatch',
        title: '导出前校验失败：租户不匹配',
        detail: '导出租户与会话租户不一致。',
        fields: [],
        tenantId: 'tenant-a',
        expectedTenantId: 'tenant-b',
        sourcePath: 'snapshot.export_precheck.issues[1]',
        raw: {},
      },
    ];

    render(<AdkExportPanel issues={issues} />);

    expect(screen.getByText('导出前安全校验（precheck）')).toBeInTheDocument();
    expect(screen.getByText('检测到敏感字段，导出被拒绝。')).toBeInTheDocument();
    expect(screen.getByText('字段: phone, id_card')).toBeInTheDocument();
    expect(screen.getByText('导出租户与会话租户不一致。')).toBeInTheDocument();
    expect(screen.getByText('租户: tenant-a / 期望: tenant-b')).toBeInTheDocument();
  });

  it('renders empty state when no issue is provided', () => {
    render(<AdkExportPanel issues={[]} emptyText="没有 precheck 拒绝" />);

    expect(screen.getByText('没有 precheck 拒绝')).toBeInTheDocument();
  });
});
