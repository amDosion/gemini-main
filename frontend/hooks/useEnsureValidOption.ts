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
    const validValues = options.map((option) => option.value);
    if (validValues.length > 0 && !validValues.includes(selected)) {
      onReset(validValues[0]);
    }
  }, [options, selected, onReset]);
};
