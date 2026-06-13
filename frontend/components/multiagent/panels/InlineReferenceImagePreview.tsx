import React from 'react';
import { X } from 'lucide-react';
import { CachedImage } from '../../common/CachedImage';
import { isSameOriginBlobUrl } from '../../../utils/safeOpen';
import { isSafeInlineImageDataUrl } from '../../../utils/safeMediaDataUrl';
import { INLINE_UPLOAD_MAX_BYTES } from '../uploadHandlers';

export interface InlineReferenceImagePreviewProps {
  imageUrl?: string | null;
  borderClassName: string;
  alt?: string;
  onClear: () => void;
}

export const isPreviewableReferenceImageUrl = (
  value: string | null | undefined,
  maxInlineBytes = INLINE_UPLOAD_MAX_BYTES
): value is string => {
  const url = (value || '').trim();
  if (!url) return false;
  if (isSafeInlineImageDataUrl(url, maxInlineBytes)) return true;
  if (isSameOriginBlobUrl(url)) return true;
  if (url.startsWith('/api/storage/')) return true;

  try {
    const parsed = new URL(url);
    return parsed.protocol === 'http:' || parsed.protocol === 'https:';
  } catch {
    return false;
  }
};

export const InlineReferenceImagePreview: React.FC<InlineReferenceImagePreviewProps> = ({
  imageUrl,
  borderClassName,
  alt = '参考图片',
  onClear,
}) => {
  if (!isPreviewableReferenceImageUrl(imageUrl)) return null;

  return (
    <div className="mb-2 relative group">
      <CachedImage
        source={{
          url: imageUrl,
          mimeType: 'image/png',
        }}
        src={imageUrl}
        alt={alt}
        className={`w-full h-24 object-cover rounded border ${borderClassName}`}
      />
      <button
        type="button"
        aria-label="清除参考图片"
        onClick={onClear}
        className="absolute top-1 right-1 p-0.5 bg-red-500/80 rounded-full text-white opacity-0 group-hover:opacity-100 transition-opacity"
      >
        <X size={10} />
      </button>
    </div>
  );
};
