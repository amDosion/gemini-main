import { describe, expect, it } from 'vitest';

import {
  extractSheetStageProtocolState,
  hasSheetStageProtocolEnvelope,
  SHEET_STAGE_PROTOCOL_VERSION,
} from './sheetStageService';

describe('sheetStageService', () => {
  it('normalizes wrapped tool result envelope into timeline and playback refs', () => {
    const snapshot = {
      toolName: 'table_analyze',
      result: {
        protocol_version: SHEET_STAGE_PROTOCOL_VERSION,
        stage: 'profile',
        status: 'completed',
        session_id: 'sheet-session-1',
        artifact: {
          artifact_key: 'sheet/profile',
          artifact_version: 2,
          artifact_session_id: 'sheet-session-1',
        },
        data: {
          next_stage: 'query',
          input_artifact: {
            artifact_key: 'sheet/ingest',
            artifact_version: 1,
            artifact_session_id: 'sheet-session-1',
          },
          history: [
            {
              stage: 'ingest',
              status: 'completed',
              artifact: {
                artifact_key: 'sheet/ingest',
                artifact_version: 1,
                artifact_session_id: 'sheet-session-1',
              },
              timestamp_ms: 1_710_000_001_000,
            },
            {
              stage: 'profile',
              status: 'completed',
              artifact: {
                artifact_key: 'sheet/profile',
                artifact_version: 2,
                artifact_session_id: 'sheet-session-1',
              },
              timestamp_ms: 1_710_000_002_000,
            },
          ],
          payload: {
            summary: { row_count: 10, column_count: 3 },
          },
        },
      },
    };

    const state = extractSheetStageProtocolState(snapshot);
    expect(state.found).toBe(true);
    expect(state.valid).toBe(true);
    expect(state.envelope?.stage).toBe('profile');
    expect(state.envelope?.sessionId).toBe('sheet-session-1');
    expect(state.envelope?.nextStage).toBe('query');
    expect(state.timeline.map((entry) => entry.stage)).toEqual(['ingest', 'profile']);
    expect(state.playbackRefs.some((entry) => entry.relation === 'input')).toBe(true);
    expect(state.playbackRefs.some((entry) => entry.relation === 'output')).toBe(true);
    expect(state.parseErrors).toEqual([]);
  });

  it('parses camelCase envelope serialized as json string and extracts precheck issues', () => {
    const envelope = {
      protocolVersion: SHEET_STAGE_PROTOCOL_VERSION,
      stage: 'export',
      status: 'completed',
      sessionId: 'sheet-session-camel',
      artifact: {
        artifactKey: 'sheet/export',
        artifactVersion: 3,
        artifactSessionId: 'sheet-session-camel',
      },
      data: {
        nextStage: 'export',
        inputArtifact: {
          artifactKey: 'sheet/query',
          artifactVersion: 2,
          artifactSessionId: 'sheet-session-camel',
        },
        history: [
          {
            stage: 'query',
            status: 'completed',
            artifact: {
              artifactKey: 'sheet/query',
              artifactVersion: 2,
              artifactSessionId: 'sheet-session-camel',
            },
            timestampMs: 1_710_000_010_000,
          },
          {
            stage: 'export',
            status: 'completed',
            artifact: {
              artifactKey: 'sheet/export',
              artifactVersion: 3,
              artifactSessionId: 'sheet-session-camel',
            },
            timestampMs: 1_710_000_011_000,
          },
        ],
        payload: {
          export_precheck: {
            issues: [
              {
                code: 'sensitive_fields',
                message: '包含敏感字段，导出被拒绝',
                fields: ['phone'],
              },
            ],
          },
        },
      },
    };

    const state = extractSheetStageProtocolState({
      payload: JSON.stringify(envelope),
    });

    expect(state.valid).toBe(true);
    expect(state.envelope?.stage).toBe('export');
    expect(state.precheckIssues).toHaveLength(1);
    expect(state.precheckIssues[0].code).toBe('sensitive_fields');
    expect(state.precheckIssues[0].fields).toEqual(['phone']);
    expect(hasSheetStageProtocolEnvelope({ payload: JSON.stringify(envelope) })).toBe(true);
  });

  it('fails closed with parse errors when candidate envelope is malformed', () => {
    const malformed = {
      protocol_version: SHEET_STAGE_PROTOCOL_VERSION,
      stage: 'query',
      status: 'completed',
      session_id: '',
      artifact: {
        artifact_key: 'sheet/query',
        artifact_version: 1,
      },
      data: {},
    };

    const state = extractSheetStageProtocolState(malformed);
    expect(state.found).toBe(true);
    expect(state.valid).toBe(false);
    expect(state.envelope).toBeNull();
    expect(state.parseErrors.some((item) => item.message.includes('session_id is required'))).toBe(true);
    expect(state.parseErrors.some((item) => item.message.includes('artifact_session_id is required'))).toBe(true);
  });

  it('keeps failed envelope visible and exposes backend error payload', () => {
    const failed = {
      wrapper: {
        protocol_version: SHEET_STAGE_PROTOCOL_VERSION,
        stage: 'profile',
        status: 'failed',
        session_id: 'sheet-session-failed',
        artifact: null,
        error: {
          code: 'SHEET_STAGE_INVALID_REQUEST',
          message: 'artifact binding mismatch',
        },
      },
    };

    const state = extractSheetStageProtocolState(failed);
    expect(state.valid).toBe(true);
    expect(state.envelope?.status).toBe('failed');
    expect(state.envelope?.error?.code).toBe('SHEET_STAGE_INVALID_REQUEST');
    expect(state.timeline).toHaveLength(1);
    expect(state.playbackRefs).toHaveLength(0);
  });

  it('returns empty state when no stage envelope exists', () => {
    const state = extractSheetStageProtocolState({
      result: {
        status: 'ok',
        message: 'plain table analyze output',
      },
    });

    expect(state.found).toBe(false);
    expect(state.valid).toBe(false);
    expect(state.envelope).toBeNull();
    expect(state.timeline).toEqual([]);
    expect(state.parseErrors).toEqual([]);
    expect(hasSheetStageProtocolEnvelope({ result: { text: 'hello' } })).toBe(false);
  });
});
