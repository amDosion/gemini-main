import {
  type MediaCacheDiagnosticEvent,
  type MediaCacheDiagnosticEventType,
  type MediaCacheDiagnosticsSnapshot,
} from './mediaCacheTypes';

const DIAGNOSTIC_EVENT_LIMIT = 200;

let diagnosticsEnabledOverride: boolean | null = null;
let diagnosticCounters: Partial<Record<MediaCacheDiagnosticEventType, number>> = {};
// Bounded ring buffer for dev-only diagnostics. We mutate `diagnosticEventRing`
// in place (writing at `diagnosticEventHead` and advancing modulo the capacity)
// so recording never allocates a new array, and the buffer can never grow past
// DIAGNOSTIC_EVENT_LIMIT entries regardless of how many events are recorded.
const diagnosticEventRing: MediaCacheDiagnosticEvent[] = [];
let diagnosticEventHead = 0;
let diagnosticEventCount = 0;

const isDevelopmentEnvironment = (): boolean => {
  try {
    return Boolean(import.meta.env?.DEV);
  } catch {
    return false;
  }
};

const isDiagnosticsEnabled = (): boolean =>
  diagnosticsEnabledOverride ?? isDevelopmentEnvironment();

export const recordDiagnostic = (
  type: MediaCacheDiagnosticEventType,
  detail: Omit<MediaCacheDiagnosticEvent, 'type' | 'timestamp'> = {}
): void => {
  if (!isDiagnosticsEnabled()) return;

  // Mutate the counter object in place (dev-only diagnostic): the public snapshot
  // returns a defensive copy, so we never need to reallocate here. This matches
  // the ring-buffer intent and avoids per-call object churn.
  diagnosticCounters[type] = (diagnosticCounters[type] || 0) + 1;

  const event: MediaCacheDiagnosticEvent = {
    type,
    ...detail,
    timestamp: Date.now(),
  };

  // Write into the ring in place; once full, overwrite the oldest slot.
  diagnosticEventRing[diagnosticEventHead] = event;
  diagnosticEventHead = (diagnosticEventHead + 1) % DIAGNOSTIC_EVENT_LIMIT;
  if (diagnosticEventCount < DIAGNOSTIC_EVENT_LIMIT) {
    diagnosticEventCount += 1;
  }
};

const readDiagnosticEventsInOrder = (): MediaCacheDiagnosticEvent[] => {
  // Materialize the ring oldest-first so consumers see chronological order.
  const ordered: MediaCacheDiagnosticEvent[] = new Array(diagnosticEventCount);
  const start = diagnosticEventCount < DIAGNOSTIC_EVENT_LIMIT ? 0 : diagnosticEventHead;
  for (let offset = 0; offset < diagnosticEventCount; offset += 1) {
    ordered[offset] = diagnosticEventRing[(start + offset) % DIAGNOSTIC_EVENT_LIMIT];
  }
  return ordered;
};

export const getMediaCacheDiagnosticsSnapshot = (): MediaCacheDiagnosticsSnapshot => ({
  enabled: isDiagnosticsEnabled(),
  counters: { ...diagnosticCounters },
  recentEvents: readDiagnosticEventsInOrder(),
});

export const resetMediaCacheDiagnostics = (): void => {
  diagnosticCounters = {};
  diagnosticEventRing.length = 0;
  diagnosticEventHead = 0;
  diagnosticEventCount = 0;
};

export const __setMediaCacheDiagnosticsEnabledForTest = (enabled: boolean | null): void => {
  diagnosticsEnabledOverride = enabled;
};

/**
 * Test-only: exposes the live internal diagnostic counters object reference.
 *
 * Used to assert that `recordDiagnostic` mutates the counter object in place
 * (ring-buffer intent) rather than reallocating a fresh object on every call.
 * Not part of the public diagnostics API; the public snapshot still returns a
 * defensive copy via `getMediaCacheDiagnosticsSnapshot`.
 */
export const __getMediaCacheDiagnosticCountersRefForTest = (): Partial<
  Record<MediaCacheDiagnosticEventType, number>
> => diagnosticCounters;
