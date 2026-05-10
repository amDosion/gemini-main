export const HISTORY_ACTION_SURFACE_SELECTOR = '[data-history-action-trigger], [data-history-action-menu]';

export const isHistoryActionSurface = (target: EventTarget | null): boolean => (
  target instanceof Element && Boolean(target.closest(HISTORY_ACTION_SURFACE_SELECTOR))
);
