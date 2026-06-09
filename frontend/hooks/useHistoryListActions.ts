import { useCallback, useEffect, useMemo, useState } from 'react';
import { db } from '../services/db';
import {
  readCachedHistoryPreference,
  readCachedHistoryStates,
  upsertCachedHistoryState,
  writeCachedHistoryPreference,
  writeCachedHistoryStates,
} from '../services/sessionCache';
import { getPrivateCacheUserScope } from '../services/privateCacheScope';
import { usePrivateCacheScopeRevision } from './usePrivateCacheScopeRevision';

interface HistoryListItem {
  id: string;
}

interface UseHistoryListActionsOptions<T extends HistoryListItem> {
  sessionId?: string | null;
  items: T[];
  onDeleteItem?: (messageId: string) => void;
}

export interface UseHistoryListActionsResult<T extends HistoryListItem> {
  showFavoritesOnly: boolean;
  setShowFavoritesOnly: (value: boolean) => void;
  filteredItems: T[];
  favoriteCount: number;
  isFavorite: (messageId: string) => boolean;
  isFavoritePending: (messageId: string) => boolean;
  toggleFavorite: (messageId: string) => Promise<void>;
  deleteItem: (messageId: string) => void;
}

export function useHistoryListActions<T extends HistoryListItem>({
  sessionId,
  items,
  onDeleteItem,
}: UseHistoryListActionsOptions<T>): UseHistoryListActionsResult<T> {
  const [favoriteIds, setFavoriteIds] = useState<Set<string>>(new Set());
  const [pendingFavoriteIds, setPendingFavoriteIds] = useState<Set<string>>(new Set());
  const [showFavoritesOnly, setShowFavoritesOnlyState] = useState(false);

  const itemIdSet = useMemo(() => new Set(items.map((item) => item.id)), [items]);

  const privateScopeRevision = usePrivateCacheScopeRevision(() => {
    setFavoriteIds(new Set());
    setPendingFavoriteIds(new Set());
    setShowFavoritesOnlyState(false);
  });

  useEffect(() => {
    let disposed = false;

    if (!sessionId) {
      setFavoriteIds(new Set());
      return () => {
        disposed = true;
      };
    }

    const cachedStates = readCachedHistoryStates(sessionId);
    if (cachedStates !== null) {
      const next = new Set<string>();
      cachedStates.forEach((state) => {
        if (state?.isFavorite && state?.messageId) {
          next.add(state.messageId);
        }
      });
      setFavoriteIds(next);
      return () => {
        disposed = true;
      };
    }

    const requestScope = getPrivateCacheUserScope();
    db.getSessionHistoryStates(sessionId)
      .then((states) => {
        if (disposed || getPrivateCacheUserScope() !== requestScope) return;

        writeCachedHistoryStates(sessionId, states);
        const next = new Set<string>();
        states.forEach((state) => {
          if (state?.isFavorite && state?.messageId) {
            next.add(state.messageId);
          }
        });
        setFavoriteIds(next);
      })
      .catch(() => {
        // 防未处理 promise rejection；db 失败时保持 favoriteIds 为空 set
      });

    return () => {
      disposed = true;
    };
  }, [privateScopeRevision, sessionId]);

  useEffect(() => {
    let disposed = false;

    if (!sessionId) {
      setShowFavoritesOnlyState(false);
      return () => {
        disposed = true;
      };
    }

    const cachedPreference = readCachedHistoryPreference(sessionId);
    if (cachedPreference !== null) {
      setShowFavoritesOnlyState(!!cachedPreference.showFavoritesOnly);
      return () => {
        disposed = true;
      };
    }

    const requestScope = getPrivateCacheUserScope();
    db.getSessionHistoryPreference(sessionId)
      .then((preference) => {
        if (disposed || getPrivateCacheUserScope() !== requestScope) return;
        writeCachedHistoryPreference(sessionId, preference);
        setShowFavoritesOnlyState(!!preference?.showFavoritesOnly);
      })
      .catch(() => {
        // 防未处理 promise rejection；db 失败时保持 showFavoritesOnly=false
      });

    return () => {
      disposed = true;
    };
  }, [privateScopeRevision, sessionId]);

  useEffect(() => {
    setFavoriteIds((prev) => {
      let changed = false;
      const next = new Set<string>();
      prev.forEach((id) => {
        if (itemIdSet.has(id)) {
          next.add(id);
        } else {
          changed = true;
        }
      });
      return changed ? next : prev;
    });
  }, [itemIdSet]);

  const isFavorite = useCallback((messageId: string) => favoriteIds.has(messageId), [favoriteIds]);
  const isFavoritePending = useCallback(
    (messageId: string) => pendingFavoriteIds.has(messageId),
    [pendingFavoriteIds]
  );

  const toggleFavorite = useCallback(
    async (messageId: string) => {
      if (!sessionId) return;

      const nextIsFavorite = !favoriteIds.has(messageId);

      setFavoriteIds((prev) => {
        const next = new Set(prev);
        if (nextIsFavorite) {
          next.add(messageId);
        } else {
          next.delete(messageId);
        }
        return next;
      });

      setPendingFavoriteIds((prev) => {
        const next = new Set(prev);
        next.add(messageId);
        return next;
      });
      const requestScope = getPrivateCacheUserScope();
      upsertCachedHistoryState(sessionId, {
        messageId,
        isFavorite: nextIsFavorite,
        updatedAt: Date.now(),
      });

      try {
        await db.updateSessionHistoryState(sessionId, messageId, { isFavorite: nextIsFavorite });
      } catch (error) {
        if (getPrivateCacheUserScope() !== requestScope) {
          return;
        }
        // rollback optimistic update
        setFavoriteIds((prev) => {
          const next = new Set(prev);
          if (nextIsFavorite) {
            next.delete(messageId);
          } else {
            next.add(messageId);
          }
          return next;
        });
        upsertCachedHistoryState(sessionId, {
          messageId,
          isFavorite: !nextIsFavorite,
          updatedAt: Date.now(),
        });
      } finally {
        if (getPrivateCacheUserScope() !== requestScope) {
          return;
        }
        setPendingFavoriteIds((prev) => {
          const next = new Set(prev);
          next.delete(messageId);
          return next;
        });
      }
    },
    [sessionId, favoriteIds]
  );

  const deleteItem = useCallback(
    (messageId: string) => {
      setFavoriteIds((prev) => {
        if (!prev.has(messageId)) return prev;
        const next = new Set(prev);
        next.delete(messageId);
        return next;
      });
      if (sessionId) {
        upsertCachedHistoryState(sessionId, {
          messageId,
          isFavorite: false,
          updatedAt: Date.now(),
        });
      }

      onDeleteItem?.(messageId);
    },
    [onDeleteItem, sessionId]
  );

  const setShowFavoritesOnly = useCallback(
    (value: boolean) => {
      setShowFavoritesOnlyState(value);
      if (!sessionId) return;

      writeCachedHistoryPreference(sessionId, {
        showFavoritesOnly: value,
        updatedAt: Date.now(),
      });
      db.updateSessionHistoryPreference(sessionId, { showFavoritesOnly: value }).catch((err) => {
        console.error('[useHistoryListActions] Failed to persist showFavoritesOnly:', err);
      });
    },
    [sessionId]
  );

  const filteredItems = useMemo(() => {
    if (!showFavoritesOnly) return items;
    return items.filter((item) => favoriteIds.has(item.id));
  }, [items, showFavoritesOnly, favoriteIds]);

  const favoriteCount = useMemo(
    () => items.reduce((count, item) => count + (favoriteIds.has(item.id) ? 1 : 0), 0),
    [items, favoriteIds]
  );

  return {
    showFavoritesOnly,
    setShowFavoritesOnly,
    filteredItems,
    favoriteCount,
    isFavorite,
    isFavoritePending,
    toggleFavorite,
    deleteItem,
  };
}
