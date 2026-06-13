import React, { useEffect, useRef } from 'react';
import { X, Download, ChevronLeft, ChevronRight } from 'lucide-react';
import { useEscapeClose } from '../../hooks/useEscapeClose';
import { CachedImage } from '../common/CachedImage';
import { downloadSourceUrlInBrowser } from '../../services/downloadService';
import { isSameOriginBlobUrl, toSafeNewTabUrl } from '../../utils/safeOpen';

interface ImageModalProps {
  isOpen: boolean;
  imageUrl: string | null;
  onClose: () => void;
  onNext?: () => void;
  onPrev?: () => void;
  hasNext?: boolean;
  hasPrev?: boolean;
}

const FOCUSABLE_SELECTOR =
  'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

const isSafeModalImageUrl = (url: string): boolean => {
  const trimmed = url.trim();
  const lowered = trimmed.toLowerCase();
  if (lowered.startsWith('/api/storage/')) return true;
  if (/^data:image\/[^;,]+;base64,/i.test(trimmed)) return true;
  if (isSameOriginBlobUrl(trimmed)) return true;
  return toSafeNewTabUrl(trimmed) !== null;
};

const ImageModal: React.FC<ImageModalProps> = ({
  isOpen,
  imageUrl,
  onClose,
  onNext,
  onPrev,
  hasNext,
  hasPrev,
}) => {
  const dialogRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<Element | null>(null);

  useEscapeClose(isOpen, onClose);

  // Capture the trigger element and lock body scroll when the modal opens.
  // Restore both when it closes.
  useEffect(() => {
    if (!isOpen) return;

    triggerRef.current = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    // Move initial focus into the dialog on the next frame so the DOM is ready.
    const frameId = requestAnimationFrame(() => {
      if (dialogRef.current) {
        const firstFocusable = dialogRef.current.querySelector<HTMLElement>(FOCUSABLE_SELECTOR);
        firstFocusable?.focus();
      }
    });

    return () => {
      cancelAnimationFrame(frameId);
      document.body.style.overflow = previousOverflow;
      if (triggerRef.current instanceof HTMLElement) {
        triggerRef.current.focus();
      }
      triggerRef.current = null;
    };
  }, [isOpen]);

  // Keyboard navigation (arrow keys) and focus trap (Tab / Shift+Tab).
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight' && hasNext && onNext) {
        onNext();
      } else if (e.key === 'ArrowLeft' && hasPrev && onPrev) {
        onPrev();
      } else if (e.key === 'Tab' && dialogRef.current) {
        const focusable = Array.from(
          dialogRef.current.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)
        );
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (e.shiftKey) {
          if (document.activeElement === first) {
            e.preventDefault();
            last.focus();
          }
        } else {
          if (document.activeElement === last) {
            e.preventDefault();
            first.focus();
          }
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, hasNext, hasPrev, onNext, onPrev]);

  const safeImageUrl = imageUrl?.trim() || null;
  if (!isOpen || !safeImageUrl || !isSafeModalImageUrl(safeImageUrl)) return null;

  const handleDownload = (e: React.MouseEvent) => {
    e.stopPropagation();
    void downloadSourceUrlInBrowser({
      sourceUrl: safeImageUrl,
      fileName: `gemini-generated-${Date.now()}.png`,
    }).catch((error) => {
      console.warn('[ImageModal] Download blocked or failed:', error);
    });
  };

  return (
    <div
      ref={dialogRef}
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/95 backdrop-blur-md animate-[fadeIn_0.2s_ease-out]"
      role="dialog"
      aria-modal="true"
      aria-label="Image preview"
      onClick={onClose}
    >
      {/* Close Button */}
      <button
        type="button"
        onClick={onClose}
        aria-label="Close"
        className="absolute top-4 right-4 p-2 text-white/70 hover:text-white bg-white/10 hover:bg-white/20 rounded-full transition-colors z-50"
      >
        <X size={24} />
      </button>

      {/* Navigation Buttons */}
      {hasPrev && (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onPrev?.();
          }}
          aria-label="Previous image"
          title="Previous Image (Left Arrow)"
          className="absolute left-4 top-1/2 -translate-y-1/2 p-3 text-white/70 hover:text-white bg-white/10 hover:bg-white/20 rounded-full transition-all hover:scale-110 z-50"
        >
          <ChevronLeft size={32} />
        </button>
      )}

      {hasNext && (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onNext?.();
          }}
          aria-label="Next image"
          title="Next Image (Right Arrow)"
          className="absolute right-4 top-1/2 -translate-y-1/2 p-3 text-white/70 hover:text-white bg-white/10 hover:bg-white/20 rounded-full transition-all hover:scale-110 z-50"
        >
          <ChevronRight size={32} />
        </button>
      )}

      {/* Main Image Container */}
      <div
        className="relative w-full h-full flex items-center justify-center p-4 md:p-12"
        onClick={(e) => e.stopPropagation()}
      >
        <CachedImage
          src={safeImageUrl}
          source={{
            url: safeImageUrl,
            mimeType: 'image/png',
          }}
          alt="Full screen preview"
          className="max-w-full max-h-full object-contain rounded-sm shadow-2xl animate-[fadeIn_0.3s_ease-out]"
        />

        {/* Footer Actions */}
        <div className="absolute bottom-6 left-1/2 -translate-x-1/2 flex items-center gap-4 px-6 py-3 bg-black/60 backdrop-blur-xl rounded-full border border-white/10 shadow-xl transition-opacity hover:opacity-100 opacity-0 md:opacity-100">
          <button
            type="button"
            onClick={handleDownload}
            className="flex items-center gap-2 text-sm font-medium text-white hover:text-indigo-300 transition-colors"
          >
            <Download size={18} />
            Download
          </button>
          <div className="w-px h-4 bg-white/20" />
          <span className="text-xs text-white/50 whitespace-nowrap">
            {safeImageUrl.startsWith('data:') ? 'Generated Result' : 'Image Preview'}
          </span>
        </div>
      </div>
    </div>
  );
};

export default ImageModal;
