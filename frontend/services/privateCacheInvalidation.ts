import { getPrivateCacheUserScope } from './privateCacheScope';

type PrivateCacheResetHandler = () => void;

export interface PrivateCacheLifecycleSnapshot {
  userScope: string;
  resetGeneration: number;
}

const resetHandlers = new Set<PrivateCacheResetHandler>();
let privateCacheResetGeneration = 0;

export const registerPrivateCacheResetHandler = (
  handler: PrivateCacheResetHandler
): (() => void) => {
  resetHandlers.add(handler);
  return () => {
    resetHandlers.delete(handler);
  };
};

export const runPrivateCacheResetHandlers = (): void => {
  privateCacheResetGeneration += 1;
  for (const handler of Array.from(resetHandlers)) {
    try {
      handler();
    } catch {
      // Cache cleanup must be best-effort so one module cannot block logout.
    }
  }
};

export const capturePrivateCacheLifecycleSnapshot = (): PrivateCacheLifecycleSnapshot => ({
  userScope: getPrivateCacheUserScope(),
  resetGeneration: privateCacheResetGeneration,
});

export const isPrivateCacheLifecycleSnapshotCurrent = (
  snapshot: PrivateCacheLifecycleSnapshot
): boolean =>
  snapshot.resetGeneration === privateCacheResetGeneration &&
  snapshot.userScope === getPrivateCacheUserScope();
