/**
 * ADK Export Precheck Issues 提取器。
 *
 * 1:1 抽离自 `adkSessionService.ts` L856-998
 * （JIRA-frontend-deep-architecture-split.md #2 Step 3）。
 */

import type { AdkExportPrecheckIssue, AdkExportPrecheckIssueCode } from './adkSessionTypes';
import {
  isRecord,
  pickFirstString,
  pickFirstValue,
  collectStringList,
  EXPORT_PRECHECK_CONTAINER_KEYS,
  EXPORT_PRECHECK_ISSUES_KEYS,
  EXPORT_PRECHECK_CODE_KEYS,
  EXPORT_PRECHECK_MESSAGE_KEYS,
  EXPORT_PRECHECK_FIELDS_KEYS,
  EXPORT_PRECHECK_TENANT_KEYS,
  EXPORT_PRECHECK_EXPECTED_TENANT_KEYS,
} from './adkSessionService';

type UnknownRecord = Record<string, unknown>;

const normalizeExportPrecheckCode = (
  rawCode: string,
  detail: string,
  fields: string[],
  record: UnknownRecord
): AdkExportPrecheckIssueCode => {
  const text = `${rawCode} ${detail}`.toLowerCase();
  const hasTenantFlag = Boolean(record.tenant_mismatch || record.tenantMismatch);
  if (hasTenantFlag || /tenant|租户/.test(text)) {
    return 'tenant_mismatch';
  }

  if (
    fields.length > 0 ||
    Boolean(record.sensitive_fields) ||
    Boolean(record.sensitiveFields) ||
    /sensitive|pii|secret|隐私|敏感/.test(text)
  ) {
    return 'sensitive_fields';
  }

  return 'unknown';
};

const buildExportPrecheckIssue = (
  record: UnknownRecord,
  sourcePath: string
): AdkExportPrecheckIssue | null => {
  const fields = EXPORT_PRECHECK_FIELDS_KEYS.flatMap((key) => collectStringList(record[key]));
  const detail = pickFirstString(record, EXPORT_PRECHECK_MESSAGE_KEYS);
  const rawCode = pickFirstString(record, EXPORT_PRECHECK_CODE_KEYS);
  const tenantId = pickFirstString(record, EXPORT_PRECHECK_TENANT_KEYS);
  const expectedTenantId = pickFirstString(record, EXPORT_PRECHECK_EXPECTED_TENANT_KEYS);
  const code = normalizeExportPrecheckCode(rawCode, detail, fields, record);

  if (code === 'unknown' && !detail && fields.length === 0 && !tenantId && !expectedTenantId) {
    return null;
  }

  const title =
    code === 'sensitive_fields'
      ? '导出前校验失败：命中敏感字段'
      : code === 'tenant_mismatch'
        ? '导出前校验失败：租户不匹配'
        : '导出前校验失败';

  const resolvedDetail =
    detail ||
    (code === 'sensitive_fields'
      ? '检测到敏感字段，导出被后端安全策略拒绝。'
      : code === 'tenant_mismatch'
        ? '检测到导出租户与会话租户不一致，导出被拒绝。'
        : '导出 precheck 未通过。');

  return {
    id: `${sourcePath}:${rawCode || code}`,
    code,
    title,
    detail: resolvedDetail,
    fields: Array.from(new Set(fields)),
    tenantId,
    expectedTenantId,
    sourcePath,
    raw: record,
  };
};

const collectExportPrecheckIssuesFromContainer = (
  container: unknown,
  sourcePath: string,
  collector: Map<string, AdkExportPrecheckIssue>
): void => {
  if (Array.isArray(container)) {
    container.forEach((item, index) => {
      if (!isRecord(item)) return;
      const issue = buildExportPrecheckIssue(item, `${sourcePath}[${index}]`);
      if (!issue) return;
      collector.set(issue.id, issue);
    });
    return;
  }

  if (!isRecord(container)) return;
  const directIssue = buildExportPrecheckIssue(container, sourcePath);
  if (directIssue) {
    collector.set(directIssue.id, directIssue);
  }

  for (const key of EXPORT_PRECHECK_ISSUES_KEYS) {
    const nested = pickFirstValue(container, [key]);
    if (Array.isArray(nested)) {
      nested.forEach((item, index) => {
        if (!isRecord(item)) return;
        const issue = buildExportPrecheckIssue(item, `${sourcePath}.${key}[${index}]`);
        if (!issue) return;
        collector.set(issue.id, issue);
      });
      continue;
    }

    if (isRecord(nested)) {
      const issue = buildExportPrecheckIssue(nested, `${sourcePath}.${key}`);
      if (issue) {
        collector.set(issue.id, issue);
      }
    }
  }
};

export const extractAdkExportPrecheckIssues = (
  sessionSnapshot: unknown
): AdkExportPrecheckIssue[] => {
  if (!sessionSnapshot) return [];

  const collector = new Map<string, AdkExportPrecheckIssue>();
  const visited = new WeakSet<object>();

  const visit = (value: unknown, path: string): void => {
    if (Array.isArray(value)) {
      value.forEach((item, index) => {
        visit(item, `${path}[${index}]`);
      });
      return;
    }

    if (!isRecord(value)) return;
    if (visited.has(value)) return;
    visited.add(value);

    for (const [key, nestedValue] of Object.entries(value)) {
      const nextPath = `${path}.${key}`;
      if (EXPORT_PRECHECK_CONTAINER_KEYS.has(key)) {
        collectExportPrecheckIssuesFromContainer(nestedValue, nextPath, collector);
      }
      visit(nestedValue, nextPath);
    }
  };

  visit(sessionSnapshot, 'snapshot');

  return Array.from(collector.values()).sort((left, right) => left.id.localeCompare(right.id));
};
