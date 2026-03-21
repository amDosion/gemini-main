import type { AdkExportPrecheckIssue } from './adkSessionService';
import {
  extractAdkExportPrecheckIssues,
  parseAdkTimestampMs,
} from './adkSessionService';

export const SHEET_STAGE_PROTOCOL_VERSION = 'sheet-stage/v1';

const SHEET_STAGE_ORDER = ['ingest', 'profile', 'query', 'export'] as const;
const SHEET_STAGE_SET = new Set<string>(SHEET_STAGE_ORDER);
const SHEET_STAGE_STATUS_SET = new Set<string>(['completed', 'failed']);

type UnknownRecord = Record<string, unknown>;

export type SheetStageName = (typeof SHEET_STAGE_ORDER)[number];
export type SheetStageStatus = 'completed' | 'failed';

export interface SheetStageArtifactRef {
  artifactKey: string;
  artifactVersion: number;
  artifactSessionId: string;
}

export interface SheetStageTimelineItem {
  id: string;
  stage: SheetStageName;
  status: SheetStageStatus;
  artifact: SheetStageArtifactRef | null;
  timestampMs: number;
  sourcePath: string;
  source: 'history' | 'current';
  raw: unknown;
}

export interface SheetStagePlaybackRef {
  id: string;
  relation: 'input' | 'output' | 'history';
  stage: SheetStageName;
  artifact: SheetStageArtifactRef;
  timestampMs: number;
  sourcePath: string;
}

export interface SheetStageProtocolError {
  sourcePath: string;
  message: string;
}

export interface SheetStageEnvelopeView {
  protocolVersion: string;
  stage: SheetStageName;
  status: SheetStageStatus;
  sessionId: string;
  artifact: SheetStageArtifactRef | null;
  inputArtifact: SheetStageArtifactRef | null;
  nextStage: SheetStageName | '';
  payload: unknown;
  error: {
    code: string;
    message: string;
  } | null;
  timeline: SheetStageTimelineItem[];
  playbackRefs: SheetStagePlaybackRef[];
  precheckIssues: AdkExportPrecheckIssue[];
  sourcePath: string;
  raw: unknown;
}

export interface SheetStageProtocolState {
  found: boolean;
  valid: boolean;
  envelope: SheetStageEnvelopeView | null;
  timeline: SheetStageTimelineItem[];
  playbackRefs: SheetStagePlaybackRef[];
  precheckIssues: AdkExportPrecheckIssue[];
  parseErrors: SheetStageProtocolError[];
}

interface EnvelopeCandidate {
  path: string;
  value: UnknownRecord;
}

interface ParsedEnvelopeCandidate {
  envelope: SheetStageEnvelopeView | null;
  parseErrors: SheetStageProtocolError[];
  score: number;
}

const EMPTY_STATE: SheetStageProtocolState = {
  found: false,
  valid: false,
  envelope: null,
  timeline: [],
  playbackRefs: [],
  precheckIssues: [],
  parseErrors: [],
};

const isRecord = (value: unknown): value is UnknownRecord =>
  Boolean(value) && typeof value === 'object' && !Array.isArray(value);

const toSafeString = (value: unknown): string => String(value ?? '').trim();

const pickFirstString = (record: UnknownRecord, keys: string[]): string => {
  for (const key of keys) {
    if (!(key in record)) continue;
    const text = toSafeString(record[key]);
    if (text) return text;
  }
  return '';
};

const pickFirstValue = (record: UnknownRecord, keys: string[]): unknown => {
  for (const key of keys) {
    if (!(key in record)) continue;
    const value = record[key];
    if (value !== undefined) return value;
  }
  return undefined;
};

const parseJsonValue = (value: string): unknown => {
  const raw = String(value || '').trim();
  if (!raw) return null;
  if (!(raw.startsWith('{') || raw.startsWith('['))) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
};

const normalizeStage = (value: unknown): SheetStageName | null => {
  const normalized = toSafeString(value).toLowerCase();
  if (!SHEET_STAGE_SET.has(normalized)) return null;
  return normalized as SheetStageName;
};

const normalizeStageStatus = (value: unknown): SheetStageStatus | null => {
  const normalized = toSafeString(value).toLowerCase();
  if (!SHEET_STAGE_STATUS_SET.has(normalized)) return null;
  return normalized as SheetStageStatus;
};

const toPositiveInteger = (value: unknown): number => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value > 0 ? Math.floor(value) : 0;
  }
  const raw = toSafeString(value);
  if (!raw) return 0;
  const numeric = Number(raw);
  if (!Number.isFinite(numeric)) return 0;
  return numeric > 0 ? Math.floor(numeric) : 0;
};

const buildArtifactIdentity = (artifact: SheetStageArtifactRef): string =>
  `${artifact.artifactKey}@${artifact.artifactVersion}:${artifact.artifactSessionId}`;

const dedupeErrors = (errors: SheetStageProtocolError[]): SheetStageProtocolError[] => {
  const seen = new Set<string>();
  const deduped: SheetStageProtocolError[] = [];
  for (const error of errors) {
    const sourcePath = toSafeString(error.sourcePath) || '$root';
    const message = toSafeString(error.message) || 'sheet stage parse error';
    const key = `${sourcePath}::${message}`;
    if (seen.has(key)) continue;
    seen.add(key);
    deduped.push({ sourcePath, message });
  }
  return deduped;
};

const parseArtifactRef = (
  value: unknown,
  sourcePath: string,
  parseErrors: SheetStageProtocolError[],
  required: boolean
): SheetStageArtifactRef | null => {
  if (value === undefined || value === null || value === '') {
    if (required) {
      parseErrors.push({
        sourcePath,
        message: 'artifact reference is required',
      });
    }
    return null;
  }
  if (!isRecord(value)) {
    parseErrors.push({
      sourcePath,
      message: 'artifact reference must be an object',
    });
    return null;
  }

  const artifactKey = pickFirstString(value, ['artifact_key', 'artifactKey']);
  if (!artifactKey) {
    parseErrors.push({
      sourcePath,
      message: 'artifact_key is required',
    });
  }

  const artifactVersion = toPositiveInteger(
    pickFirstValue(value, ['artifact_version', 'artifactVersion'])
  );
  if (artifactVersion <= 0) {
    parseErrors.push({
      sourcePath,
      message: 'artifact_version must be >= 1',
    });
  }

  const artifactSessionId = pickFirstString(value, [
    'artifact_session_id',
    'artifactSessionId',
  ]);
  if (!artifactSessionId) {
    parseErrors.push({
      sourcePath,
      message: 'artifact_session_id is required',
    });
  }

  if (!artifactKey || artifactVersion <= 0 || !artifactSessionId) {
    return null;
  }
  return {
    artifactKey,
    artifactVersion,
    artifactSessionId,
  };
};

const parseTimelineHistory = (
  value: unknown,
  sourcePath: string,
  parseErrors: SheetStageProtocolError[]
): SheetStageTimelineItem[] => {
  if (value === undefined || value === null) {
    return [];
  }
  if (!Array.isArray(value)) {
    parseErrors.push({
      sourcePath,
      message: 'history must be an array',
    });
    return [];
  }

  const timeline: SheetStageTimelineItem[] = [];
  value.forEach((item, index) => {
    const itemPath = `${sourcePath}[${index}]`;
    if (!isRecord(item)) {
      parseErrors.push({
        sourcePath: itemPath,
        message: 'history entry must be an object',
      });
      return;
    }

    const stage = normalizeStage(item.stage);
    if (!stage) {
      parseErrors.push({
        sourcePath: `${itemPath}.stage`,
        message: `invalid stage: ${toSafeString(item.stage) || '<empty>'}`,
      });
      return;
    }

    const status = normalizeStageStatus(item.status);
    if (!status) {
      parseErrors.push({
        sourcePath: `${itemPath}.status`,
        message: `invalid status: ${toSafeString(item.status) || '<empty>'}`,
      });
      return;
    }

    const artifact = parseArtifactRef(item.artifact, `${itemPath}.artifact`, parseErrors, false);
    const timestampMs = parseAdkTimestampMs(
      pickFirstValue(item, [
        'timestamp_ms',
        'timestampMs',
        'timestamp',
        'created_at_ms',
        'createdAtMs',
        'created_at',
        'createdAt',
      ])
    );

    timeline.push({
      id: `history:${index}:${stage}:${artifact ? buildArtifactIdentity(artifact) : 'none'}`,
      stage,
      status,
      artifact,
      timestampMs,
      sourcePath: itemPath,
      source: 'history',
      raw: item,
    });
  });

  return timeline;
};

const mergeTimelineWithCurrent = ({
  history,
  stage,
  status,
  artifact,
  sourcePath,
  raw,
}: {
  history: SheetStageTimelineItem[];
  stage: SheetStageName;
  status: SheetStageStatus;
  artifact: SheetStageArtifactRef | null;
  sourcePath: string;
  raw: unknown;
}): SheetStageTimelineItem[] => {
  const deduped = [...history];
  const currentIdentity = artifact ? buildArtifactIdentity(artifact) : 'none';
  const currentItem: SheetStageTimelineItem = {
    id: `current:${stage}:${currentIdentity}`,
    stage,
    status,
    artifact,
    timestampMs: 0,
    sourcePath,
    source: 'current',
    raw,
  };

  const duplicateIndex = deduped.findIndex((item) => {
    const sameStage = item.stage === currentItem.stage;
    const sameStatus = item.status === currentItem.status;
    const leftIdentity = item.artifact ? buildArtifactIdentity(item.artifact) : 'none';
    return sameStage && sameStatus && leftIdentity === currentIdentity;
  });

  if (duplicateIndex >= 0) {
    const existing = deduped[duplicateIndex];
    deduped[duplicateIndex] = {
      ...currentItem,
      timestampMs: existing.timestampMs,
    };
    return deduped;
  }

  deduped.push(currentItem);
  return deduped;
};

const buildPlaybackRefs = ({
  stage,
  outputArtifact,
  inputArtifact,
  timeline,
  sourcePath,
}: {
  stage: SheetStageName;
  outputArtifact: SheetStageArtifactRef | null;
  inputArtifact: SheetStageArtifactRef | null;
  timeline: SheetStageTimelineItem[];
  sourcePath: string;
}): SheetStagePlaybackRef[] => {
  const refs: SheetStagePlaybackRef[] = [];
  const seen = new Set<string>();

  const push = (ref: SheetStagePlaybackRef) => {
    const key = `${ref.relation}:${buildArtifactIdentity(ref.artifact)}:${ref.stage}`;
    if (seen.has(key)) return;
    seen.add(key);
    refs.push(ref);
  };

  if (inputArtifact) {
    push({
      id: `input:${buildArtifactIdentity(inputArtifact)}`,
      relation: 'input',
      stage,
      artifact: inputArtifact,
      timestampMs: 0,
      sourcePath: `${sourcePath}.data.input_artifact`,
    });
  }

  if (outputArtifact) {
    push({
      id: `output:${buildArtifactIdentity(outputArtifact)}`,
      relation: 'output',
      stage,
      artifact: outputArtifact,
      timestampMs: 0,
      sourcePath: `${sourcePath}.artifact`,
    });
  }

  timeline.forEach((item, index) => {
    if (!item.artifact) return;
    push({
      id: `history:${index}:${buildArtifactIdentity(item.artifact)}`,
      relation: 'history',
      stage: item.stage,
      artifact: item.artifact,
      timestampMs: item.timestampMs,
      sourcePath: item.sourcePath,
    });
  });

  return refs;
};

const parseEnvelopeCandidate = (candidate: EnvelopeCandidate): ParsedEnvelopeCandidate => {
  const parseErrors: SheetStageProtocolError[] = [];
  const record = candidate.value;
  const protocolVersion = pickFirstString(record, ['protocol_version', 'protocolVersion']);
  const stage = normalizeStage(record.stage);
  const status = normalizeStageStatus(record.status);
  const sessionId = pickFirstString(record, ['session_id', 'sessionId']);
  let hasFatalError = false;

  if (!protocolVersion) {
    hasFatalError = true;
    parseErrors.push({
      sourcePath: `${candidate.path}.protocol_version`,
      message: 'protocol_version is required',
    });
  } else if (protocolVersion !== SHEET_STAGE_PROTOCOL_VERSION) {
    hasFatalError = true;
    parseErrors.push({
      sourcePath: `${candidate.path}.protocol_version`,
      message: `unsupported protocol_version: ${protocolVersion}`,
    });
  }

  if (!stage) {
    hasFatalError = true;
    parseErrors.push({
      sourcePath: `${candidate.path}.stage`,
      message: `invalid stage: ${toSafeString(record.stage) || '<empty>'}`,
    });
  }

  if (!status) {
    hasFatalError = true;
    parseErrors.push({
      sourcePath: `${candidate.path}.status`,
      message: `invalid status: ${toSafeString(record.status) || '<empty>'}`,
    });
  }

  if (!sessionId) {
    hasFatalError = true;
    parseErrors.push({
      sourcePath: `${candidate.path}.session_id`,
      message: 'session_id is required',
    });
  }

  const dataValue = record.data;
  let dataRecord: UnknownRecord | null = null;
  if (dataValue !== undefined && dataValue !== null) {
    if (!isRecord(dataValue)) {
      hasFatalError = true;
      parseErrors.push({
        sourcePath: `${candidate.path}.data`,
        message: 'data must be an object',
      });
    } else {
      dataRecord = dataValue;
    }
  }

  const artifact = parseArtifactRef(
    record.artifact,
    `${candidate.path}.artifact`,
    parseErrors,
    status === 'completed'
  );

  const inputArtifact = parseArtifactRef(
    dataRecord
      ? pickFirstValue(dataRecord, ['input_artifact', 'inputArtifact'])
      : undefined,
    `${candidate.path}.data.input_artifact`,
    parseErrors,
    false
  );

  const nextStageRaw = dataRecord
    ? pickFirstString(dataRecord, ['next_stage', 'nextStage'])
    : '';
  let nextStage: SheetStageName | '' = '';
  if (nextStageRaw) {
    const normalizedNextStage = normalizeStage(nextStageRaw);
    if (!normalizedNextStage) {
      parseErrors.push({
        sourcePath: `${candidate.path}.data.next_stage`,
        message: `invalid next_stage: ${nextStageRaw}`,
      });
    } else {
      nextStage = normalizedNextStage;
    }
  }

  const timeline = mergeTimelineWithCurrent({
    history: parseTimelineHistory(
      dataRecord ? dataRecord.history : undefined,
      `${candidate.path}.data.history`,
      parseErrors
    ),
    stage: stage || 'ingest',
    status: status || 'failed',
    artifact,
    sourcePath: candidate.path,
    raw: record,
  });

  const errorValue = record.error;
  let error: SheetStageEnvelopeView['error'] = null;
  if (errorValue !== undefined && errorValue !== null) {
    if (isRecord(errorValue)) {
      error = {
        code: pickFirstString(errorValue, ['code', 'error_code', 'errorCode']),
        message: pickFirstString(errorValue, ['message', 'detail', 'reason']),
      };
    } else {
      error = {
        code: '',
        message: toSafeString(errorValue),
      };
    }
  }

  const precheckIssues = extractAdkExportPrecheckIssues(record);
  const envelope =
    hasFatalError || !stage || !status || !sessionId || !protocolVersion
      ? null
      : {
          protocolVersion,
          stage,
          status,
          sessionId,
          artifact,
          inputArtifact,
          nextStage,
          payload: dataRecord ? dataRecord.payload : undefined,
          error,
          timeline,
          playbackRefs: buildPlaybackRefs({
            stage,
            outputArtifact: artifact,
            inputArtifact,
            timeline,
            sourcePath: candidate.path,
          }),
          precheckIssues,
          sourcePath: candidate.path,
          raw: record,
        };

  return {
    envelope,
    parseErrors: dedupeErrors(parseErrors),
    score: envelope
      ? (envelope.timeline.length * 10)
        + envelope.playbackRefs.length
        + (envelope.status === 'completed' ? 1 : 0)
      : 0,
  };
};

const isEnvelopeCandidateRecord = (record: UnknownRecord): boolean => {
  const hasProtocolKey = ('protocol_version' in record) || ('protocolVersion' in record);
  if (hasProtocolKey) return true;

  const hasStage = 'stage' in record;
  const hasStatus = 'status' in record;
  const hasSession = ('session_id' in record) || ('sessionId' in record);
  const hasArtifact = 'artifact' in record;
  return hasStage && hasStatus && hasSession && hasArtifact;
};

const collectEnvelopeCandidates = (snapshot: unknown): EnvelopeCandidate[] => {
  const candidates: EnvelopeCandidate[] = [];
  const visited = new Set<unknown>();

  const walk = (value: unknown, sourcePath: string, depth: number) => {
    if (depth > 14 || value === null || value === undefined) {
      return;
    }
    if (typeof value === 'string') {
      const parsed = parseJsonValue(value);
      if (parsed !== null) {
        walk(parsed, `${sourcePath}#json`, depth + 1);
      }
      return;
    }
    if (Array.isArray(value)) {
      value.forEach((item, index) => {
        walk(item, `${sourcePath}[${index}]`, depth + 1);
      });
      return;
    }
    if (!isRecord(value)) {
      return;
    }
    if (visited.has(value)) return;
    visited.add(value);

    if (isEnvelopeCandidateRecord(value)) {
      candidates.push({
        path: sourcePath,
        value,
      });
    }

    Object.entries(value).forEach(([key, nested]) => {
      walk(nested, `${sourcePath}.${key}`, depth + 1);
    });
  };

  walk(snapshot, '$root', 0);
  return candidates;
};

export const extractSheetStageProtocolState = (snapshot: unknown): SheetStageProtocolState => {
  const candidates = collectEnvelopeCandidates(snapshot);
  if (candidates.length === 0) {
    return EMPTY_STATE;
  }

  const parsed = candidates.map((candidate) => parseEnvelopeCandidate(candidate));
  const validCandidates = parsed.filter((item) => item.envelope !== null);
  if (validCandidates.length === 0) {
    return {
      ...EMPTY_STATE,
      found: true,
      parseErrors: dedupeErrors(parsed.flatMap((item) => item.parseErrors)),
    };
  }

  const best = validCandidates
    .slice()
    .sort((left, right) => {
      if (right.score !== left.score) {
        return right.score - left.score;
      }
      return left.parseErrors.length - right.parseErrors.length;
    })[0];

  const envelope = best.envelope;
  if (!envelope) {
    return {
      ...EMPTY_STATE,
      found: true,
      parseErrors: best.parseErrors,
    };
  }

  return {
    found: true,
    valid: true,
    envelope,
    timeline: envelope.timeline,
    playbackRefs: envelope.playbackRefs,
    precheckIssues: envelope.precheckIssues,
    parseErrors: best.parseErrors,
  };
};

export const hasSheetStageProtocolEnvelope = (snapshot: unknown): boolean =>
  extractSheetStageProtocolState(snapshot).valid;
