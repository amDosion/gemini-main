import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import {
  releaseMediaObjectUrl,
  retainMediaObjectUrl,
} from '../services/mediaCache';

const isBlobObjectUrl = (value: string | null | undefined): boolean =>
  String(value || '').trim().toLowerCase().startsWith('blob:');

export const useRetainedBlobObjectUrlState = (
  initialSrc: string | null
): readonly [
  string | null,
  (nextSrc: string | null) => void,
] => {
  const initialBlobSrc = isBlobObjectUrl(initialSrc) ? initialSrc : null;
  const initialBlobSrcRef = useRef<string | null>(initialBlobSrc);
  const [src, setSrc] = useState<string | null>(initialBlobSrc ? null : initialSrc);
  const retainedBlobSrcRef = useRef<string | null>(null);
  const preRetainedBlobSrcRef = useRef<string | null>(null);

  const retainBlobBeforeExpose = useCallback((nextSrc: string | null) => {
    const nextBlobSrc = isBlobObjectUrl(nextSrc) ? nextSrc : null;
    const preRetainedBlobSrc = preRetainedBlobSrcRef.current;
    const retainedBlobSrc = retainedBlobSrcRef.current;

    if (
      preRetainedBlobSrc &&
      preRetainedBlobSrc !== nextBlobSrc &&
      preRetainedBlobSrc !== retainedBlobSrc
    ) {
      preRetainedBlobSrcRef.current = null;
      releaseMediaObjectUrl(preRetainedBlobSrc);
    }

    if (
      !nextBlobSrc ||
      nextBlobSrc === retainedBlobSrc ||
      nextBlobSrc === preRetainedBlobSrcRef.current
    ) {
      return;
    }

    retainMediaObjectUrl(nextBlobSrc);
    preRetainedBlobSrcRef.current = nextBlobSrc;
  }, []);

  const setRetainedSrc = useCallback(
    (nextSrc: string | null) => {
      retainBlobBeforeExpose(nextSrc);
      setSrc(nextSrc);
    },
    [retainBlobBeforeExpose]
  );

  const releaseRetainedBlobRefs = useCallback(() => {
    const preRetainedBlobSrc = preRetainedBlobSrcRef.current;
    const retainedBlobSrc = retainedBlobSrcRef.current;
    preRetainedBlobSrcRef.current = null;
    retainedBlobSrcRef.current = null;

    if (preRetainedBlobSrc) {
      releaseMediaObjectUrl(preRetainedBlobSrc);
    }
    if (retainedBlobSrc && retainedBlobSrc !== preRetainedBlobSrc) {
      releaseMediaObjectUrl(retainedBlobSrc);
    }
  }, []);

  useLayoutEffect(() => {
    if (initialBlobSrcRef.current && src === null) {
      setRetainedSrc(initialBlobSrcRef.current);
      initialBlobSrcRef.current = null;
      return;
    }
    initialBlobSrcRef.current = null;

    const nextBlobSrc = isBlobObjectUrl(src) ? src : null;
    const previousBlobSrc = retainedBlobSrcRef.current;

    if (nextBlobSrc && previousBlobSrc !== nextBlobSrc) {
      if (preRetainedBlobSrcRef.current === nextBlobSrc) {
        preRetainedBlobSrcRef.current = null;
      } else {
        retainMediaObjectUrl(nextBlobSrc);
      }
      retainedBlobSrcRef.current = nextBlobSrc;
    }

    if (previousBlobSrc && previousBlobSrc !== nextBlobSrc) {
      releaseMediaObjectUrl(previousBlobSrc);
    }

    if (!nextBlobSrc) {
      retainedBlobSrcRef.current = null;
      const preRetainedBlobSrc = preRetainedBlobSrcRef.current;
      if (preRetainedBlobSrc) {
        preRetainedBlobSrcRef.current = null;
        releaseMediaObjectUrl(preRetainedBlobSrc);
      }
    }
  }, [setRetainedSrc, src]);

  useEffect(() => releaseRetainedBlobRefs, [releaseRetainedBlobRefs]);

  return [src, setRetainedSrc] as const;
};
