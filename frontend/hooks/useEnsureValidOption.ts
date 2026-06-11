import { useEffect } from 'react';

/**
 * Keeps a selected value within a list of available options.
 *
 * When `options` is non-empty and no longer contains `selected`, resets the
 * selection to the first available option. While the list is empty (e.g. a mode
 * controls schema is still loading) the current value is left untouched.
 *
 * Extracted from the duplicated size/quality validation effects shared by the
 * mode control panels (grok VideoGenControls / ImageGenControls, ...).
 */
export const useEnsureValidOption = (
  selected: string,
  options: ReadonlyArray<{ value: string }>,
  onReset: (next: string) => void
): void => {
  useEffect(() => {
    if (options.length > 0 && !options.some((option) => option.value === selected)) {
      onReset(options[0].value);
    }
  }, [options, selected, onReset]);
};
