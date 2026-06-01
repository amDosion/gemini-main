import type { ModeControlsSchema } from '../../hooks/useModeControlsSchema';

export const getUnsupportedParams = (
  schema: ModeControlsSchema | null | undefined
): Set<string> => {
  const raw = schema?.constraints?.unsupported_params;
  if (!Array.isArray(raw)) {
    return new Set();
  }
  return new Set(raw.filter((item): item is string => typeof item === 'string'));
};

export const supportsBooleanParam = (
  schema: ModeControlsSchema | null | undefined,
  paramName: string
): boolean => {
  const options = schema?.paramOptions?.[paramName] ?? [];
  return (
    options.some((option) => typeof option.value === 'boolean') ||
    typeof schema?.defaults?.[paramName] === 'boolean'
  );
};

export const getBooleanDefault = (
  schema: ModeControlsSchema | null | undefined,
  paramName: string,
  fallback: boolean
): boolean => {
  const value = schema?.defaults?.[paramName];
  return typeof value === 'boolean' ? value : fallback;
};
