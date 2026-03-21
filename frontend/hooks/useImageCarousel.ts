import { useCallback, useEffect, useMemo, useState } from 'react';

export interface UseImageCarouselOptions {
  itemCount: number;
  initialIndex?: number;
  resetKey?: string | number | null;
  keyboardEnabled?: boolean;
  onNavigate?: () => void;
}

export interface UseImageCarouselReturn {
  index: number;
  setIndex: (index: number) => void;
  goPrev: () => void;
  goNext: () => void;
  select: (index: number) => void;
  hasMultiple: boolean;
  total: number;
  currentNumber: number;
}

const normalizeIndex = (index: number, itemCount: number): number => {
  if (itemCount <= 0) return 0;
  const modulo = ((index % itemCount) + itemCount) % itemCount;
  return modulo;
};

const isTextEditingTarget = (target: EventTarget | null): boolean => {
  if (!(target instanceof HTMLElement)) {
    return false;
  }
  if (target.isContentEditable) {
    return true;
  }
  const tagName = target.tagName;
  return tagName === 'INPUT' || tagName === 'TEXTAREA' || tagName === 'SELECT';
};

export function useImageCarousel(options: UseImageCarouselOptions): UseImageCarouselReturn {
  const {
    itemCount,
    initialIndex = 0,
    resetKey,
    keyboardEnabled = true,
    onNavigate
  } = options;

  const safeCount = Math.max(0, itemCount);
  const [index, setRawIndex] = useState(() => normalizeIndex(initialIndex, safeCount));

  const setIndex = useCallback((nextIndex: number) => {
    setRawIndex(normalizeIndex(nextIndex, safeCount));
  }, [safeCount]);

  const goPrev = useCallback(() => {
    if (safeCount <= 1) return;
    setRawIndex((prev) => normalizeIndex(prev - 1, safeCount));
    onNavigate?.();
  }, [safeCount, onNavigate]);

  const goNext = useCallback(() => {
    if (safeCount <= 1) return;
    setRawIndex((prev) => normalizeIndex(prev + 1, safeCount));
    onNavigate?.();
  }, [safeCount, onNavigate]);

  const select = useCallback((nextIndex: number) => {
    if (safeCount <= 0) return;
    setRawIndex(normalizeIndex(nextIndex, safeCount));
    onNavigate?.();
  }, [safeCount, onNavigate]);

  useEffect(() => {
    setRawIndex((prev) => normalizeIndex(prev, safeCount));
  }, [safeCount]);

  useEffect(() => {
    if (resetKey === undefined) {
      return;
    }
    setRawIndex(normalizeIndex(initialIndex, safeCount));
  }, [resetKey, initialIndex, safeCount]);

  useEffect(() => {
    if (!keyboardEnabled || safeCount <= 1) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (isTextEditingTarget(event.target)) {
        return;
      }
      if (event.key === 'ArrowLeft') {
        event.preventDefault();
        goPrev();
      } else if (event.key === 'ArrowRight') {
        event.preventDefault();
        goNext();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [keyboardEnabled, safeCount, goPrev, goNext]);

  const result = useMemo<UseImageCarouselReturn>(() => ({
    index,
    setIndex,
    goPrev,
    goNext,
    select,
    hasMultiple: safeCount > 1,
    total: safeCount,
    currentNumber: safeCount > 0 ? index + 1 : 0
  }), [index, setIndex, goPrev, goNext, select, safeCount]);

  return result;
}

export default useImageCarousel;
