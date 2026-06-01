import { useEffect, useRef, useState } from 'react';
import { registerPrivateCacheResetHandler } from '../services/privateCacheInvalidation';
import { subscribePrivateCacheUserScope } from '../services/privateCacheScope';

type PrivateCacheScopeChangeHandler = () => void;

interface PrivateCacheLifecycleRevisionOptions {
  includeCacheReset?: boolean;
}

export function usePrivateCacheLifecycleRevision(
  onLifecycleChange?: PrivateCacheScopeChangeHandler,
  options: PrivateCacheLifecycleRevisionOptions = {}
): number {
  const { includeCacheReset = false } = options;
  const [revision, setRevision] = useState(0);
  const onLifecycleChangeRef = useRef<PrivateCacheScopeChangeHandler | undefined>(onLifecycleChange);

  useEffect(() => {
    onLifecycleChangeRef.current = onLifecycleChange;
  }, [onLifecycleChange]);

  const bumpRevision = () => {
    onLifecycleChangeRef.current?.();
    setRevision((current) => current + 1);
  };

  useEffect(
    () =>
      subscribePrivateCacheUserScope(bumpRevision),
    []
  );

  useEffect(() => {
    if (!includeCacheReset) {
      return undefined;
    }
    return registerPrivateCacheResetHandler(bumpRevision);
  }, [includeCacheReset]);

  return revision;
}

export function usePrivateCacheScopeRevision(
  onScopeChange?: PrivateCacheScopeChangeHandler
): number {
  return usePrivateCacheLifecycleRevision(onScopeChange);
}
