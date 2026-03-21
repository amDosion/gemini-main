export type TelemetryEventType = 'web-vital' | 'span' | 'error';

export interface FrontendTelemetryEvent {
  type: TelemetryEventType;
  name: string;
  value?: number;
  unit?: string;
  timestamp: number;
  tags?: Record<string, string | number | boolean>;
  detail?: Record<string, unknown>;
}

export interface TelemetryLogger {
  log: (event: FrontendTelemetryEvent) => void;
}

export interface TelemetrySpan {
  end: (
    status?: 'ok' | 'error',
    detail?: Record<string, unknown>,
    tags?: Record<string, string | number | boolean>,
  ) => void;
}

interface TelemetryBootstrapOptions {
  logger?: TelemetryLogger;
}

const MAX_BUFFER_SIZE = 200;
const cleanupTasks: Array<() => void> = [];
const eventBuffer: FrontendTelemetryEvent[] = [];

let telemetryStarted = false;
let activeLogger: TelemetryLogger = {
  log: (event) => {
    if (import.meta.env.DEV) {
      console.info('[frontend-telemetry]', event);
    }
  },
};

const nowMs = () => Date.now();

const nowPerf = () => {
  if (typeof performance !== 'undefined' && typeof performance.now === 'function') {
    return performance.now();
  }
  return nowMs();
};

const emitEvent = (event: FrontendTelemetryEvent) => {
  activeLogger.log(event);
  eventBuffer.push(event);
  if (eventBuffer.length > MAX_BUFFER_SIZE) {
    eventBuffer.shift();
  }

  if (typeof window !== 'undefined') {
    (window as any).__frontendTelemetryBuffer = [...eventBuffer];
    window.dispatchEvent(new CustomEvent('frontend-telemetry', { detail: event }));
  }
};

const observeEntries = (
  options: PerformanceObserverInit,
  onEntries: (entries: PerformanceEntry[]) => void,
): (() => void) => {
  if (typeof window === 'undefined' || typeof window.PerformanceObserver === 'undefined') {
    return () => undefined;
  }

  try {
    const observer = new PerformanceObserver((list) => {
      onEntries(list.getEntries());
    });
    observer.observe(options);
    return () => observer.disconnect();
  } catch {
    return () => undefined;
  }
};

const collectNavigationMetrics = () => {
  if (typeof performance === 'undefined' || typeof performance.getEntriesByType !== 'function') {
    return;
  }

  const navEntry = performance.getEntriesByType('navigation')[0] as PerformanceNavigationTiming | undefined;
  if (!navEntry) return;

  emitEvent({
    type: 'web-vital',
    name: 'ttfb',
    value: navEntry.responseStart,
    unit: 'ms',
    timestamp: nowMs(),
  });

  emitEvent({
    type: 'web-vital',
    name: 'dom-content-loaded',
    value: navEntry.domContentLoadedEventEnd,
    unit: 'ms',
    timestamp: nowMs(),
  });

  emitEvent({
    type: 'web-vital',
    name: 'load-event-end',
    value: navEntry.loadEventEnd,
    unit: 'ms',
    timestamp: nowMs(),
  });
};

const setupPaintObserver = () => observeEntries(
  { type: 'paint', buffered: true },
  (entries) => {
    entries.forEach((entry) => {
      if (entry.name !== 'first-paint' && entry.name !== 'first-contentful-paint') return;
      emitEvent({
        type: 'web-vital',
        name: entry.name,
        value: entry.startTime,
        unit: 'ms',
        timestamp: nowMs(),
      });
    });
  },
);

const setupLcpObserver = () => {
  let latestLcp: PerformanceEntry | null = null;

  const observerCleanup = observeEntries(
    { type: 'largest-contentful-paint', buffered: true },
    (entries) => {
      if (entries.length > 0) {
        latestLcp = entries[entries.length - 1];
      }
    },
  );

  const reportLcp = () => {
    if (!latestLcp) return;
    emitEvent({
      type: 'web-vital',
      name: 'lcp',
      value: latestLcp.startTime,
      unit: 'ms',
      timestamp: nowMs(),
    });
    latestLcp = null;
  };

  const onVisibilityChange = () => {
    if (document.visibilityState === 'hidden') {
      reportLcp();
    }
  };

  const onPageHide = () => reportLcp();

  if (typeof document !== 'undefined') {
    document.addEventListener('visibilitychange', onVisibilityChange, { once: true });
  }
  if (typeof window !== 'undefined') {
    window.addEventListener('pagehide', onPageHide, { once: true });
  }

  return () => {
    observerCleanup();
    if (typeof document !== 'undefined') {
      document.removeEventListener('visibilitychange', onVisibilityChange);
    }
    if (typeof window !== 'undefined') {
      window.removeEventListener('pagehide', onPageHide);
    }
  };
};

const setupClsObserver = () => {
  let clsValue = 0;
  let reported = false;

  const observerCleanup = observeEntries(
    { type: 'layout-shift', buffered: true },
    (entries) => {
      entries.forEach((entry) => {
        const shift = entry as any;
        if (shift?.hadRecentInput) return;
        clsValue += Number(shift?.value || 0);
      });
    },
  );

  const reportCls = () => {
    if (reported) return;
    reported = true;
    emitEvent({
      type: 'web-vital',
      name: 'cls',
      value: Number(clsValue.toFixed(4)),
      unit: 'score',
      timestamp: nowMs(),
    });
  };

  const onVisibilityChange = () => {
    if (document.visibilityState === 'hidden') {
      reportCls();
    }
  };

  const onPageHide = () => reportCls();

  if (typeof document !== 'undefined') {
    document.addEventListener('visibilitychange', onVisibilityChange, { once: true });
  }
  if (typeof window !== 'undefined') {
    window.addEventListener('pagehide', onPageHide, { once: true });
  }

  return () => {
    observerCleanup();
    if (typeof document !== 'undefined') {
      document.removeEventListener('visibilitychange', onVisibilityChange);
    }
    if (typeof window !== 'undefined') {
      window.removeEventListener('pagehide', onPageHide);
    }
  };
};

const setupFirstInputObserver = () => observeEntries(
  { type: 'first-input', buffered: true },
  (entries) => {
    const firstInput = entries[0] as any;
    if (!firstInput) return;
    const fid = Number(firstInput.processingStart || 0) - Number(firstInput.startTime || 0);
    emitEvent({
      type: 'web-vital',
      name: 'fid',
      value: Number(fid.toFixed(2)),
      unit: 'ms',
      timestamp: nowMs(),
    });
  },
);

export const startFrontendTelemetry = (options: TelemetryBootstrapOptions = {}) => {
  if (options.logger) {
    activeLogger = options.logger;
  }
  if (telemetryStarted) {
    return;
  }
  telemetryStarted = true;

  collectNavigationMetrics();
  cleanupTasks.push(setupPaintObserver());
  cleanupTasks.push(setupLcpObserver());
  cleanupTasks.push(setupClsObserver());
  cleanupTasks.push(setupFirstInputObserver());
};

export const stopFrontendTelemetry = () => {
  while (cleanupTasks.length > 0) {
    const cleanup = cleanupTasks.pop();
    cleanup?.();
  }
  telemetryStarted = false;
};

export const startTelemetrySpan = (
  name: string,
  detail: Record<string, unknown> = {},
  tags: Record<string, string | number | boolean> = {},
): TelemetrySpan => {
  const startedAt = nowPerf();
  const startedTimestamp = nowMs();
  let finished = false;

  return {
    end: (status = 'ok', endDetail = {}, endTags = {}) => {
      if (finished) return;
      finished = true;

      const duration = Math.max(0, nowPerf() - startedAt);
      emitEvent({
        type: 'span',
        name,
        value: Number(duration.toFixed(2)),
        unit: 'ms',
        timestamp: nowMs(),
        tags: {
          ...tags,
          ...endTags,
          status,
        },
        detail: {
          ...detail,
          ...endDetail,
          startedAt: startedTimestamp,
        },
      });
    },
  };
};

export const captureFrontendError = (
  error: unknown,
  detail: Record<string, unknown> = {},
  tags: Record<string, string | number | boolean> = {},
) => {
  const normalized = error instanceof Error ? error : new Error(String(error));

  emitEvent({
    type: 'error',
    name: normalized.name || 'Error',
    timestamp: nowMs(),
    tags,
    detail: {
      message: normalized.message,
      stack: normalized.stack,
      ...detail,
    },
  });
};

