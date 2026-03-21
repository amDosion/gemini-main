import { requestJson } from '../../services/http';
import { parseAdkTimestampMs } from './adkSessionService';
import {
  extractSheetStageProtocolState,
  SHEET_STAGE_PROTOCOL_VERSION,
  type SheetStageArtifactRef,
  type SheetStageEnvelopeView,
  type SheetStageName,
  type SheetStageProtocolError,
  type SheetStageTimelineItem,
} from './sheetStageService';

type UnknownRecord = Record<string, unknown>;

const STAGE_SET = new Set<SheetStageName>(['ingest', 'profile', 'query', 'export']);

const STAGE_LABELS: Record<SheetStageName, string> = {
  ingest: 'Ingest',
  profile: 'Profile',
  query: 'Query',
  export: 'Export',
};

const isRecord = (value: unknown): value is UnknownRecord =>
  Boolean(value) && typeof value === 'object' && !Array.isArray(value);

const toSafeString = (value: unknown): string => String(value ?? '').trim();

const toArtifactIdentity = (artifact: SheetStageArtifactRef): string =>
  `${artifact.artifactKey}@${artifact.artifactVersion}:${artifact.artifactSessionId}`;

const parseMaybeJson = (value: unknown): unknown => {
  if (typeof value !== 'string') {
    return value;
  }
  const raw = value.trim();
  if (!raw || !(raw.startsWith('{') || raw.startsWith('['))) {
    return value;
  }
  try {
    return JSON.parse(raw);
  } catch {
    return value;
  }
};

const normalizeStage = (value: unknown): SheetStageName | null => {
  const normalized = toSafeString(value).toLowerCase();
  if (!STAGE_SET.has(normalized as SheetStageName)) {
    return null;
  }
  return normalized as SheetStageName;
};

const pickFirstValue = (record: UnknownRecord, keys: string[]): unknown => {
  for (const key of keys) {
    if (!(key in record)) continue;
    const value = record[key];
    if (value !== undefined) {
      return value;
    }
  }
  return undefined;
};

const pickFirstString = (record: UnknownRecord, keys: string[]): string => {
  const raw = pickFirstValue(record, keys);
  return toSafeString(raw);
};

const parseArtifactRef = (value: unknown): SheetStageArtifactRef | null => {
  if (!isRecord(value)) {
    return null;
  }
  const artifactKey = pickFirstString(value, ['artifact_key', 'artifactKey']);
  const rawVersion = pickFirstValue(value, ['artifact_version', 'artifactVersion']);
  const artifactVersion = Number(rawVersion);
  const artifactSessionId = pickFirstString(value, ['artifact_session_id', 'artifactSessionId']);
  if (!artifactKey || !Number.isFinite(artifactVersion) || artifactVersion <= 0 || !artifactSessionId) {
    return null;
  }
  return {
    artifactKey,
    artifactVersion: Math.floor(artifactVersion),
    artifactSessionId,
  };
};

const resolveQueryText = (payload: unknown): string => {
  if (!isRecord(payload)) {
    return '';
  }
  return pickFirstString(payload, ['query', 'query_text', 'queryText']);
};

const resolveExportFormat = (payload: unknown): string => {
  if (!isRecord(payload)) {
    return '';
  }
  return pickFirstString(payload, ['export_format', 'exportFormat']);
};

const formatTimestamp = (timestampMs: number): string => {
  if (!Number.isFinite(timestampMs) || timestampMs <= 0) {
    return '-';
  }
  return new Date(timestampMs).toLocaleString();
};

export interface StageReplayAnchor {
  id: string;
  stage: SheetStageName;
  stageLabel: string;
  status: SheetStageTimelineItem['status'];
  timestampMs: number;
  timestampLabel: string;
  artifact: SheetStageArtifactRef;
  inputArtifact: SheetStageArtifactRef | null;
  invocationId: string;
  originalPayload: unknown;
  canReplay: boolean;
  blockedReason: string;
  sourcePath: string;
}

export interface StageReplayContext {
  valid: boolean;
  message: string;
  sessionId: string;
  timeline: SheetStageTimelineItem[];
  anchors: StageReplayAnchor[];
  parseErrors: SheetStageProtocolError[];
}

export type StageReplayDiffChange = 'added' | 'removed' | 'changed';

export interface StageReplayDiffEntry {
  path: string;
  change: StageReplayDiffChange;
  originalPreview: string;
  replayedPreview: string;
}

export interface StageReplayResult {
  anchor: StageReplayAnchor;
  replayEnvelope: SheetStageEnvelopeView;
  originalPayload: unknown;
  replayedPayload: unknown;
  diff: StageReplayDiffEntry[];
  requestedAtMs: number;
}

interface StageReplayEnvelopeRecord {
  stage: SheetStageName;
  status: 'completed' | 'failed';
  sessionId: string;
  artifact: SheetStageArtifactRef | null;
  inputArtifact: SheetStageArtifactRef | null;
  invocationId: string;
  payload: unknown;
  sourcePath: string;
  timestampMs: number;
}

const isEnvelopeCandidateRecord = (record: UnknownRecord): boolean => {
  const hasStage = 'stage' in record;
  const hasStatus = 'status' in record;
  const hasSession = 'session_id' in record || 'sessionId' in record;
  const hasArtifact = 'artifact' in record;
  return hasStage && hasStatus && hasSession && hasArtifact;
};

const parseEnvelopeRecord = (value: unknown, sourcePath: string): StageReplayEnvelopeRecord | null => {
  if (!isRecord(value) || !isEnvelopeCandidateRecord(value)) {
    return null;
  }

  const protocolVersion = pickFirstString(value, ['protocol_version', 'protocolVersion']);
  if (protocolVersion && protocolVersion !== SHEET_STAGE_PROTOCOL_VERSION) {
    return null;
  }

  const stage = normalizeStage(value.stage);
  const status = toSafeString(value.status).toLowerCase();
  const sessionId = pickFirstString(value, ['session_id', 'sessionId']);
  if (!stage || (status !== 'completed' && status !== 'failed') || !sessionId) {
    return null;
  }

  const data = isRecord(value.data) ? value.data : null;
  const resume = data && isRecord(data.resume) ? data.resume : null;
  const invocationId = resume
    ? pickFirstString(resume, ['invocation_id', 'invocationId'])
    : pickFirstString(value, ['invocation_id', 'invocationId']);

  const timestampMs = parseAdkTimestampMs(
    pickFirstValue(value, [
      'updated_at_ms',
      'updatedAtMs',
      'updated_at',
      'updatedAt',
      'timestamp_ms',
      'timestampMs',
      'timestamp',
      'created_at_ms',
      'createdAtMs',
      'created_at',
      'createdAt',
    ])
  );

  return {
    stage,
    status,
    sessionId,
    artifact: parseArtifactRef(value.artifact),
    inputArtifact: data ? parseArtifactRef(pickFirstValue(data, ['input_artifact', 'inputArtifact'])) : null,
    invocationId,
    payload: data ? data.payload : undefined,
    sourcePath,
    timestampMs,
  };
};

const collectEnvelopeRecords = (snapshot: unknown): StageReplayEnvelopeRecord[] => {
  const candidates: StageReplayEnvelopeRecord[] = [];
  const visited = new Set<unknown>();

  const walk = (value: unknown, sourcePath: string, depth: number) => {
    if (depth > 14 || value === null || value === undefined) {
      return;
    }

    const normalized = parseMaybeJson(value);
    if (Array.isArray(normalized)) {
      normalized.forEach((item, index) => {
        walk(item, `${sourcePath}[${index}]`, depth + 1);
      });
      return;
    }

    if (!isRecord(normalized)) {
      return;
    }

    if (visited.has(normalized)) {
      return;
    }
    visited.add(normalized);

    const candidate = parseEnvelopeRecord(normalized, sourcePath);
    if (candidate) {
      candidates.push(candidate);
    }

    Object.entries(normalized).forEach(([key, nested]) => {
      walk(nested, `${sourcePath}.${key}`, depth + 1);
    });
  };

  walk(snapshot, '$root', 0);
  return candidates;
};

const buildAnchorBlockedReason = (record: StageReplayEnvelopeRecord | null, timelineItem: SheetStageTimelineItem): string => {
  if (timelineItem.status !== 'completed') {
    return '仅支持 completed 阶段作为回放锚点。';
  }

  if (timelineItem.stage === 'ingest') {
    return 'ingest 阶段缺少可复用输入源，已按 fail-closed 禁止回放。';
  }

  if (!record) {
    return '未定位到对应的原始阶段 envelope，无法执行回放差异对比。';
  }

  if (!record.inputArtifact) {
    return '原始阶段缺少 input_artifact，无法构造回放请求。';
  }

  if (record.payload === undefined) {
    return '原始阶段缺少 payload，无法展示回放差异。';
  }

  if (timelineItem.stage === 'query' && !resolveQueryText(record.payload)) {
    return 'query 阶段缺少 query 字段，无法安全回放。';
  }

  if (timelineItem.stage === 'export' && !resolveExportFormat(record.payload)) {
    return 'export 阶段缺少 export_format 字段，无法安全回放。';
  }

  return '';
};

const toPreviewText = (value: unknown): string => {
  if (value === undefined) {
    return '<undefined>';
  }
  if (typeof value === 'string') {
    return value.length > 180 ? `${value.slice(0, 180)}...` : value;
  }
  try {
    const serialized = JSON.stringify(value);
    if (!serialized) {
      return '<empty>';
    }
    return serialized.length > 180 ? `${serialized.slice(0, 180)}...` : serialized;
  } catch {
    return String(value);
  }
};

const appendDiffEntries = (
  originalValue: unknown,
  replayedValue: unknown,
  path: string,
  entries: StageReplayDiffEntry[],
  maxEntries: number
): void => {
  if (entries.length >= maxEntries || Object.is(originalValue, replayedValue)) {
    return;
  }

  if (Array.isArray(originalValue) && Array.isArray(replayedValue)) {
    const maxLength = Math.max(originalValue.length, replayedValue.length);
    for (let index = 0; index < maxLength && entries.length < maxEntries; index += 1) {
      appendDiffEntries(
        originalValue[index],
        replayedValue[index],
        `${path}[${index}]`,
        entries,
        maxEntries
      );
    }
    return;
  }

  if (isRecord(originalValue) && isRecord(replayedValue)) {
    const keys = Array.from(new Set([...Object.keys(originalValue), ...Object.keys(replayedValue)])).sort();
    keys.forEach((key) => {
      if (entries.length >= maxEntries) return;
      const nextPath = path === '$' ? `$.${key}` : `${path}.${key}`;
      appendDiffEntries(originalValue[key], replayedValue[key], nextPath, entries, maxEntries);
    });
    return;
  }

  const change: StageReplayDiffChange =
    originalValue === undefined
      ? 'added'
      : replayedValue === undefined
        ? 'removed'
        : 'changed';

  entries.push({
    path,
    change,
    originalPreview: toPreviewText(originalValue),
    replayedPreview: toPreviewText(replayedValue),
  });
};

export const buildStageReplayDiff = (
  originalValue: unknown,
  replayedValue: unknown,
  maxEntries: number = 80
): StageReplayDiffEntry[] => {
  const entries: StageReplayDiffEntry[] = [];
  appendDiffEntries(originalValue, replayedValue, '$', entries, Math.max(1, Math.floor(maxEntries)));
  return entries;
};

const buildReplayRequestBody = (context: StageReplayContext, anchor: StageReplayAnchor): UnknownRecord => {
  if (!anchor.canReplay || !anchor.inputArtifact) {
    throw new Error(anchor.blockedReason || '当前锚点不可回放');
  }

  const body: UnknownRecord = {
    protocolVersion: SHEET_STAGE_PROTOCOL_VERSION,
    stage: anchor.stage,
    sessionId: context.sessionId,
    artifact: {
      artifact_key: anchor.inputArtifact.artifactKey,
      artifact_version: anchor.inputArtifact.artifactVersion,
      artifact_session_id: anchor.inputArtifact.artifactSessionId,
    },
  };

  if (anchor.invocationId) {
    body.invocationId = anchor.invocationId;
  }

  if (anchor.stage === 'query') {
    const query = resolveQueryText(anchor.originalPayload);
    if (!query) {
      throw new Error('query 阶段原始 payload 缺少 query 字段，已拒绝回放。');
    }
    body.query = query;
  }

  if (anchor.stage === 'export') {
    const exportFormat = resolveExportFormat(anchor.originalPayload);
    if (!exportFormat) {
      throw new Error('export 阶段原始 payload 缺少 export_format 字段，已拒绝回放。');
    }
    body.exportFormat = exportFormat;
  }

  return body;
};

export const getPreferredReplayAnchorId = (anchors: StageReplayAnchor[]): string =>
  anchors.find((item) => item.canReplay)?.id || anchors[0]?.id || '';

export const extractStageReplayContext = (
  snapshot: unknown,
  fallbackSessionId: string = ''
): StageReplayContext => {
  const stageState = extractSheetStageProtocolState(snapshot);

  if (!stageState.found) {
    return {
      valid: false,
      message: '当前会话未检测到 sheet-stage/v1 协议数据，已按 fail-closed 禁用回放。',
      sessionId: toSafeString(fallbackSessionId),
      timeline: [],
      anchors: [],
      parseErrors: [],
    };
  }

  if (!stageState.valid || !stageState.envelope) {
    return {
      valid: false,
      message: '检测到阶段协议响应但结构无效，已按 fail-closed 禁用回放。',
      sessionId: toSafeString(fallbackSessionId),
      timeline: stageState.timeline,
      anchors: [],
      parseErrors: stageState.parseErrors,
    };
  }

  const sessionId = toSafeString(stageState.envelope.sessionId || fallbackSessionId);
  if (!sessionId) {
    return {
      valid: false,
      message: '会话缺少 session_id，已按 fail-closed 禁用回放。',
      sessionId: '',
      timeline: stageState.timeline,
      anchors: [],
      parseErrors: stageState.parseErrors,
    };
  }

  const envelopeRecords = collectEnvelopeRecords(snapshot);
  const envelopeByArtifact = new Map<string, StageReplayEnvelopeRecord>();
  envelopeRecords.forEach((record) => {
    if (!record.artifact) return;
    if (record.sessionId !== sessionId) return;
    const identity = toArtifactIdentity(record.artifact);
    const existing = envelopeByArtifact.get(identity);
    if (!existing || record.timestampMs >= existing.timestampMs) {
      envelopeByArtifact.set(identity, record);
    }
  });

  const anchors = stageState.timeline
    .filter((item) => item.artifact !== null)
    .map((item, index) => {
      const artifact = item.artifact as SheetStageArtifactRef;
      const identity = toArtifactIdentity(artifact);
      const record = envelopeByArtifact.get(identity) || null;
      const blockedReason = buildAnchorBlockedReason(record, item);
      const timestampMs = item.timestampMs || record?.timestampMs || 0;
      return {
        id: `anchor:${index}:${item.id}`,
        stage: item.stage,
        stageLabel: STAGE_LABELS[item.stage],
        status: item.status,
        timestampMs,
        timestampLabel: formatTimestamp(timestampMs),
        artifact,
        inputArtifact: record?.inputArtifact || null,
        invocationId: record?.invocationId || '',
        originalPayload: record?.payload,
        canReplay: !blockedReason,
        blockedReason,
        sourcePath: record?.sourcePath || item.sourcePath,
      } as StageReplayAnchor;
    });

  if (anchors.length === 0) {
    return {
      valid: false,
      message: '历史阶段时间线缺少 artifact，无法生成 replay 锚点。',
      sessionId,
      timeline: stageState.timeline,
      anchors,
      parseErrors: stageState.parseErrors,
    };
  }

  if (!anchors.some((anchor) => anchor.canReplay)) {
    return {
      valid: false,
      message: '已识别历史阶段，但缺少可回放锚点，回放入口保持禁用。',
      sessionId,
      timeline: stageState.timeline,
      anchors,
      parseErrors: stageState.parseErrors,
    };
  }

  return {
    valid: true,
    message: `已加载 ${anchors.length} 个历史锚点，可选择阶段执行回放。`,
    sessionId,
    timeline: stageState.timeline,
    anchors,
    parseErrors: stageState.parseErrors,
  };
};

export const replayStageFromAnchor = async (
  context: StageReplayContext,
  anchorId: string,
  signal?: AbortSignal
): Promise<StageReplayResult> => {
  if (!context.valid) {
    throw new Error(context.message || '当前会话回放上下文无效。');
  }

  const anchor = context.anchors.find((item) => item.id === anchorId);
  if (!anchor) {
    throw new Error('未找到指定 replay 锚点。');
  }

  if (!anchor.canReplay) {
    throw new Error(anchor.blockedReason || '当前锚点不可回放。');
  }

  const requestBody = buildReplayRequestBody(context, anchor);

  const response = await requestJson<any>(
    '/api/multi-agent/workflows/excel-analysis/stage',
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestBody),
      signal,
      timeoutMs: 0,
      withAuth: true,
      credentials: 'include',
    }
  );

  const replayState = extractSheetStageProtocolState(response);
  if (!replayState.valid || !replayState.envelope) {
    throw new Error('回放响应不符合 sheet-stage/v1 合同，已拒绝展示。');
  }

  if (replayState.envelope.status !== 'completed') {
    const backendMessage = toSafeString(replayState.envelope.error?.message);
    throw new Error(backendMessage || `回放执行失败（status=${replayState.envelope.status}）。`);
  }

  if (replayState.envelope.stage !== anchor.stage) {
    throw new Error('回放返回阶段与锚点不一致，已按 fail-closed 拒绝展示。');
  }

  if (toSafeString(replayState.envelope.sessionId) !== context.sessionId) {
    throw new Error('回放返回 session_id 与当前会话不一致，已按 fail-closed 拒绝展示。');
  }

  if (anchor.originalPayload === undefined) {
    throw new Error('原始阶段 payload 缺失，无法生成差异视图。');
  }

  const replayedPayload = replayState.envelope.payload;
  const diff = buildStageReplayDiff(anchor.originalPayload, replayedPayload);

  return {
    anchor,
    replayEnvelope: replayState.envelope,
    originalPayload: anchor.originalPayload,
    replayedPayload,
    diff,
    requestedAtMs: Date.now(),
  };
};
