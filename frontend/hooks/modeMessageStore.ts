import { useCallback, useSyncExternalStore } from 'react';
import { AppMode, Message } from '../types/types';

const EMPTY: Message[] = Object.freeze([]) as unknown as Message[];
const cells = new Map<AppMode, Message[]>();
const listeners = new Map<AppMode, Set<() => void>>();

export function getModeMessages(mode: AppMode): Message[] {
  return cells.get(mode) ?? EMPTY;
}

export type MessagesUpdater = Message[] | ((prev: Message[]) => Message[]);

export function setModeMessages(mode: AppMode, updater: MessagesUpdater): void {
  const prev = cells.get(mode) ?? EMPTY;
  const next =
    typeof updater === 'function' ? (updater as (p: Message[]) => Message[])(prev) : updater;
  if (next === prev) return;
  cells.set(mode, next);
  const subs = listeners.get(mode);
  if (subs) subs.forEach((listener) => listener());
}

function subscribeMode(mode: AppMode, cb: () => void): () => void {
  let set = listeners.get(mode);
  if (!set) {
    set = new Set();
    listeners.set(mode, set);
  }
  set.add(cb);
  return () => {
    set!.delete(cb);
  };
}

/** 重置全部 cell(用户/Profile 切换时调用,避免跨用户陈旧数据)。 */
export function resetModeMessages(): void {
  const affected = Array.from(listeners.keys());
  cells.clear();
  for (const mode of affected) listeners.get(mode)?.forEach((listener) => listener());
}

export function useModeMessages(mode: AppMode): Message[] {
  const subscribe = useCallback((cb: () => void) => subscribeMode(mode, cb), [mode]);
  const getSnapshot = useCallback(() => getModeMessages(mode), [mode]);
  return useSyncExternalStore(subscribe, getSnapshot, getSnapshot);
}
