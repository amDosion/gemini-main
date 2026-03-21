import { useEffect } from 'react';

/**
 * Reusable ESC-to-close behavior for dialogs/modals.
 *
 * Usage:
 *   useEscapeClose(isOpen, onClose)
 */
export function useEscapeClose(
  isOpen: boolean,
  onClose: () => void,
  enabled: boolean = true
) {
  useEffect(() => {
    if (!isOpen || !enabled) return;

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      event.preventDefault();
      event.stopPropagation();
      onClose();
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [isOpen, onClose, enabled]);
}

export default useEscapeClose;
