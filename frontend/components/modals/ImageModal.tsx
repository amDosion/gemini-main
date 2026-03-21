
import React, { useEffect } from 'react';
import { X, Download, ChevronLeft, ChevronRight } from 'lucide-react';
import { useEscapeClose } from '../../hooks/useEscapeClose';

interface ImageModalProps {
  isOpen: boolean;
  imageUrl: string | null;
  onClose: () => void;
  onNext?: () => void;
  onPrev?: () => void;
  hasNext?: boolean;
  hasPrev?: boolean;
}

const ImageModal: React.FC<ImageModalProps> = ({ 
  isOpen, 
  imageUrl, 
  onClose,
  onNext,
  onPrev,
  hasNext,
  hasPrev
}) => {
  useEscapeClose(isOpen, onClose);

  // Keyboard navigation
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight' && hasNext && onNext) {
        onNext();
      } else if (e.key === 'ArrowLeft' && hasPrev && onPrev) {
        onPrev();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, hasNext, hasPrev, onNext, onPrev]);

  if (!isOpen || !imageUrl) return null;

  const handleDownload = (e: React.MouseEvent) => {
    e.stopPropagation();
    const link = document.createElement('a');
    link.href = imageUrl;
    link.download = `gemini-generated-${Date.now()}.png`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/95 backdrop-blur-md animate-[fadeIn_0.2s_ease-out]" onClick={onClose}>
      
      {/* Close Button */}
      <button 
        onClick={onClose}
        className="absolute top-4 right-4 p-2 text-white/70 hover:text-white bg-white/10 hover:bg-white/20 rounded-full transition-colors z-50"
      >
        <X size={24} />
      </button>

      {/* Navigation Buttons */}
      {hasPrev && (
        <button
          onClick={(e) => { e.stopPropagation(); onPrev?.(); }}
          className="absolute left-4 top-1/2 -translate-y-1/2 p-3 text-white/70 hover:text-white bg-white/10 hover:bg-white/20 rounded-full transition-all hover:scale-110 z-50"
          title="Previous Image (Left Arrow)"
        >
          <ChevronLeft size={32} />
        </button>
      )}

      {hasNext && (
        <button
          onClick={(e) => { e.stopPropagation(); onNext?.(); }}
          className="absolute right-4 top-1/2 -translate-y-1/2 p-3 text-white/70 hover:text-white bg-white/10 hover:bg-white/20 rounded-full transition-all hover:scale-110 z-50"
          title="Next Image (Right Arrow)"
        >
          <ChevronRight size={32} />
        </button>
      )}

      {/* Main Image Container */}
      <div className="relative w-full h-full flex items-center justify-center p-4 md:p-12" onClick={e => e.stopPropagation()}>
        <img 
          src={imageUrl} 
          alt="Full screen preview" 
          className="max-w-full max-h-full object-contain rounded-sm shadow-2xl animate-[fadeIn_0.3s_ease-out]"
        />
        
        {/* Footer Actions */}
        <div className="absolute bottom-6 left-1/2 -translate-x-1/2 flex items-center gap-4 px-6 py-3 bg-black/60 backdrop-blur-xl rounded-full border border-white/10 shadow-xl transition-opacity hover:opacity-100 opacity-0 md:opacity-100">
           <button 
             onClick={handleDownload}
             className="flex items-center gap-2 text-sm font-medium text-white hover:text-indigo-300 transition-colors"
           >
             <Download size={18} />
             Download
           </button>
           <div className="w-px h-4 bg-white/20" />
           <span className="text-xs text-white/50 whitespace-nowrap">
             {imageUrl.startsWith('data:') ? 'Generated Result' : 'Image Preview'}
           </span>
        </div>
      </div>
    </div>
  );
};

export default ImageModal;
