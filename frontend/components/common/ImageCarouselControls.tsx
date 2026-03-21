import React, { useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight, Image as ImageIcon } from 'lucide-react';

export type CarouselAccentTone = 'emerald' | 'orange' | 'pink' | 'indigo' | 'slate';

export interface CarouselMediaItem {
  id?: string | number;
  url?: string | null;
  thumbUrl?: string | null;
  alt?: string;
}

interface ImageCarouselArrowsProps {
  itemCount: number;
  onPrev: () => void;
  onNext: () => void;
  prevTitle?: string;
  nextTitle?: string;
}

const ACCENT_CLASSES: Record<CarouselAccentTone, { ring: string; overlay: string }> = {
  emerald: { ring: 'ring-emerald-500', overlay: 'bg-emerald-500/20' },
  orange: { ring: 'ring-orange-500', overlay: 'bg-orange-500/20' },
  pink: { ring: 'ring-pink-500', overlay: 'bg-pink-500/20' },
  indigo: { ring: 'ring-indigo-500', overlay: 'bg-indigo-500/20' },
  slate: { ring: 'ring-slate-500', overlay: 'bg-slate-500/20' }
};

export const ImageCarouselArrows: React.FC<ImageCarouselArrowsProps> = ({
  itemCount,
  onPrev,
  onNext,
  prevTitle = '上一张',
  nextTitle = '下一张'
}) => {
  if (itemCount <= 1) {
    return null;
  }

  return (
    <>
      <button
        onClick={onPrev}
        className="absolute left-4 z-10 p-3 rounded-full bg-black/50 hover:bg-black/70 text-white backdrop-blur border border-white/10 transition-all hover:scale-110"
        title={prevTitle}
      >
        <ChevronLeft size={24} />
      </button>
      <button
        onClick={onNext}
        className="absolute right-4 z-10 p-3 rounded-full bg-black/50 hover:bg-black/70 text-white backdrop-blur border border-white/10 transition-all hover:scale-110"
        title={nextTitle}
      >
        <ChevronRight size={24} />
      </button>
    </>
  );
};

interface ImageCarouselThumbnailsProps {
  items: CarouselMediaItem[];
  currentIndex: number;
  onSelect: (index: number) => void;
  accentTone?: CarouselAccentTone;
  thumbnailSize?: number;
  panelClassName?: string;
  counterClassName?: string;
  showCounter?: boolean;
}

export const ImageCarouselThumbnails: React.FC<ImageCarouselThumbnailsProps> = ({
  items,
  currentIndex,
  onSelect,
  accentTone = 'emerald',
  thumbnailSize = 64,
  panelClassName = 'flex items-center gap-3 py-4 px-4',
  counterClassName = 'ml-2 text-sm text-slate-400 font-mono',
  showCounter = true
}) => {
  const [failedThumbs, setFailedThumbs] = useState<Record<number, boolean>>({});
  const accent = ACCENT_CLASSES[accentTone] || ACCENT_CLASSES.emerald;

  const thumbStyle = useMemo<React.CSSProperties>(() => ({
    width: `${thumbnailSize}px`,
    height: `${thumbnailSize}px`
  }), [thumbnailSize]);

  if (items.length <= 1) {
    return null;
  }

  return (
    <div className={panelClassName}>
      {items.map((item, idx) => {
        const key = item.id ?? idx;
        const thumbUrl = item.thumbUrl || item.url || '';
        const showPlaceholder = !thumbUrl || failedThumbs[idx];
        const isCurrent = idx === currentIndex;

        return (
          <button
            key={key}
            onClick={() => onSelect(idx)}
            className={`relative rounded-lg overflow-hidden transition-all duration-200 ${
              isCurrent ? `ring-2 ${accent.ring} scale-110` : 'opacity-60 hover:opacity-100 hover:scale-105'
            }`}
            style={thumbStyle}
            title={`切换到第 ${idx + 1} 张`}
          >
            {!showPlaceholder && (
              <img
                src={thumbUrl}
                className="w-full h-full object-cover"
                alt={item.alt || `缩略图 ${idx + 1}`}
                onError={() => setFailedThumbs((prev) => ({ ...prev, [idx]: true }))}
              />
            )}
            {showPlaceholder && (
              <div className="w-full h-full bg-slate-800 flex items-center justify-center">
                <ImageIcon size={Math.max(16, Math.floor(thumbnailSize * 0.3))} className="text-slate-600" />
              </div>
            )}
            {isCurrent && (
              <div className={`absolute inset-0 ${accent.overlay}`} />
            )}
          </button>
        );
      })}

      {showCounter && (
        <span className={counterClassName}>
          {currentIndex + 1} / {items.length}
        </span>
      )}
    </div>
  );
};

export default ImageCarouselThumbnails;
