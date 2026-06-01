import { useLayoutEffect } from 'react';
import {
  releaseMediaObjectUrl,
  retainMediaObjectUrl,
} from '../services/mediaCache';

const isBlobObjectUrl = (value: string | null | undefined): boolean =>
  String(value || '').trim().toLowerCase().startsWith('blob:');

export const useRetainedBlobObjectUrl = (objectUrl: string | null | undefined): void => {
  useLayoutEffect(() => {
    if (!isBlobObjectUrl(objectUrl)) return undefined;

    retainMediaObjectUrl(objectUrl);
    return () => {
      releaseMediaObjectUrl(objectUrl);
    };
  }, [objectUrl]);
};
