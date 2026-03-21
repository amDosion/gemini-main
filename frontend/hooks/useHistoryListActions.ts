import { useCallback, useEffect, useMemo, useState } from 'react';
import { db } from '../services/db';

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

  useEffect(() => {
    let disposed = false;

    if (!sessionId) {
      setFavoriteIds(new Set());
      return () => {
        disposed = true;
      };
    }

    db.getSessionHistoryStates(sessionId)
      .then((states) => {
        if (disposed) return;

        const next = new Set<string>();
        states.forEach((state) => {
          if (state?.isFavorite && state?.messageId) {
            next.add(state.messageId);
          }
        });
        setFavoriteIds(next);
      })
      .catch((error) => {
        console.warn('[useHistoryListActions] 获取收藏状态失败:', error);
      });

    return () => {
      disposed = true;
    };
  }, [sessionId]);

  useEffect(() => {
    let disposed = false;

    if (!sessionId) {
      setShowFavoritesOnlyState(false);
      return () => {
        disposed = true;
      };
    }

    db.getSessionHistoryPreference(sessionId)
      .then((preference) => {
        if (disposed) return;
        setShowFavoritesOnlyState(!!preference?.showFavoritesOnly);
      })
      .catch((error) => {
        console.warn('[useHistoryListActions] 获取历史偏好失败:', error);
      });

    return () => {
      disposed = true;
    };
  }, [sessionId]);

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

  const toggleFavorite = useCallback(async (messageId: string) => {
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

    try {
      await db.updateSessionHistoryState(sessionId, messageId, { isFavorite: nextIsFavorite });
    } catch (error) {
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
      console.warn('[useHistoryListActions] 更新收藏状态失败:', error);
    } finally {
      setPendingFavoriteIds((prev) => {
        const next = new Set(prev);
        next.delete(messageId);
        return next;
      });
    }
  }, [sessionId, favoriteIds]);

  const deleteItem = useCallback((messageId: string) => {
    setFavoriteIds((prev) => {
      if (!prev.has(messageId)) return prev;
      const next = new Set(prev);
      next.delete(messageId);
      return next;
    });

    onDeleteItem?.(messageId);
  }, [onDeleteItem]);

  const setShowFavoritesOnly = useCallback((value: boolean) => {
    setShowFavoritesOnlyState(value);
    if (!sessionId) return;

    db.updateSessionHistoryPreference(sessionId, { showFavoritesOnly: value })
      .catch((error) => {
        console.warn('[useHistoryListActions] 更新历史偏好失败:', error);
      });
  }, [sessionId]);

  const filteredItems = useMemo(() => {
    if (!showFavoritesOnly) return items;
    return items.filter((item) => favoriteIds.has(item.id));
  }, [items, showFavoritesOnly, favoriteIds]);

  const favoriteCount = useMemo(() => {
    let count = 0;
    items.forEach((item) => {
      if (favoriteIds.has(item.id)) {
        count += 1;
      }
    });
    return count;
  }, [items, favoriteIds]);

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
