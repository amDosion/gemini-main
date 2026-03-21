export const PREVIEW_IMAGE_MAX_ENTRIES = 40;
const INLINE_MEDIA_DATA_URL_MAX_CHARS = 4096;

const stripMarkdownCodeFence = (text: string): string => {
  let normalized = String(text || '').trim();
  const matched = normalized.match(/^```(?:json|markdown|md|text)?\s*([\s\S]*?)\s*```$/i);
  if (matched) {
    normalized = matched[1].trim();
  }
  return normalized;
};

export const isLikelyImageUrl = (value: string) => {
  if (!value) return false;
  if (/^(data:image\/|blob:)/.test(value)) return true;
  if (/^https?:\/\//.test(value) || value.startsWith('/')) {
    const normalized = value.toLowerCase().split('?')[0].split('#')[0];
    if (/\.(png|jpg|jpeg|webp|gif|bmp|svg)$/.test(normalized)) return true;
    if (/(image|images|uploads|attachments|generated|edited|expanded)/.test(normalized)) return true;
  }
  return false;
};

const createLikelyMediaUrlMatcher = (extensions: RegExp, pathHints: RegExp, dataPrefix: RegExp) => (value: string) => {
  if (!value) return false;
  if (dataPrefix.test(value) || /^blob:/i.test(value)) return true;
  if (/^https?:\/\//.test(value) || value.startsWith('/')) {
    const normalized = value.toLowerCase().split('?')[0].split('#')[0];
    if (extensions.test(normalized)) return true;
    if (pathHints.test(normalized)) return true;
  }
  return false;
};

export const isLikelyAudioUrl = createLikelyMediaUrlMatcher(
  /\.(mp3|wav|m4a|aac|flac|ogg|opus)$/i,
  /(audio|speech|voice|tts|narration|podcast)/i,
  /^data:audio\//i
);

export const isLikelyVideoUrl = createLikelyMediaUrlMatcher(
  /\.(mp4|mov|webm|avi|mkv|m4v)$/i,
  /(video|videos|veo|movie|clip|render)/i,
  /^data:video\//i
);

const isTempAttachmentUrl = (value: string) => {
  const normalized = String(value || '').trim().toLowerCase();
  if (!normalized) return false;
  if (normalized.startsWith('/api/temp-images/')) return true;
  return /^(https?:\/\/[^/]+)?\/api\/temp-images\/[^/?#]+/i.test(normalized);
};

const inferMediaMimeType = (payload: Record<string, unknown>): string => {
  if (!isPlainObject(payload)) return '';
  const mimeType = payload.mimeType ?? payload.mime_type ?? payload.contentType ?? payload.content_type;
  return typeof mimeType === 'string' ? mimeType.trim().toLowerCase() : '';
};

export const isPlaceholderImageInput = (value: string) => {
  const normalized = String(value || '').trim().toLowerCase();
  if (!normalized) return true;
  if (normalized.includes('{{') || normalized.includes('}}')) return true;
  if (normalized.includes('example.com') || normalized.includes('example.org')) return true;
  if (/<[^>]+>/.test(normalized)) return true;
  if (/(your[-_\s]?image|upload.*image|placeholder|sample[-_\s]?image)/.test(normalized)) return true;
  return false;
};

export const hasUsableImageInput = (value: unknown) => {
  if (typeof value !== 'string') return false;
  const normalized = value.trim();
  if (!normalized) return false;
  if (isPlaceholderImageInput(normalized)) return false;
  return isLikelyImageUrl(normalized) || /^https?:\/\//.test(normalized);
};

export const isPlainObject = (value: unknown): value is Record<string, unknown> => {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value));
};

export const normalizeImageValue = (value: unknown) => {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  if (!trimmed) return null;
  if (isLikelyImageUrl(trimmed)) return trimmed;
  const compact = trimmed.replace(/\s+/g, '');
  if (compact.length >= 128 && /^[A-Za-z0-9+/=]+$/.test(compact)) {
    return `data:image/png;base64,${compact}`;
  }
  return null;
};

export const isLocalFilesystemPath = (value: string) => {
  const normalized = String(value || '').trim();
  if (!normalized) return false;
  if (/^[a-zA-Z]:\\/.test(normalized)) return true;
  return /^\/(?:Users|home|var|private|opt|tmp|mnt|Volumes)\//.test(normalized);
};

export const isDirectlyRenderableImageUrl = (value: unknown) => {
  if (typeof value !== 'string') return false;
  const normalized = value.trim();
  if (!normalized) return false;
  if (normalized.startsWith('data:image/') || normalized.startsWith('blob:')) return true;
  if (/^https?:\/\//.test(normalized)) return true;
  if (normalized.startsWith('/')) {
    return !isLocalFilesystemPath(normalized);
  }
  return false;
};

const isRenderableInlineMediaUrl = (normalized: string, prefix: 'data:audio/' | 'data:video/') => {
  return normalized.startsWith(prefix) && normalized.length <= INLINE_MEDIA_DATA_URL_MAX_CHARS;
};

const isDirectlyRenderableMediaUrl = (value: unknown, prefix: 'data:audio/' | 'data:video/') => {
  if (typeof value !== 'string') return false;
  const normalized = value.trim();
  if (!normalized) return false;
  if (isRenderableInlineMediaUrl(normalized, prefix) || normalized.startsWith('blob:')) return true;
  if (/^https?:\/\//.test(normalized)) return true;
  if (normalized.startsWith('/')) {
    return !isLocalFilesystemPath(normalized);
  }
  return false;
};

export const isDirectlyRenderableAudioUrl = (value: unknown) =>
  isDirectlyRenderableMediaUrl(value, 'data:audio/');

export const isDirectlyRenderableVideoUrl = (value: unknown) =>
  isDirectlyRenderableMediaUrl(value, 'data:video/');

export const extractImageUrls = (value: unknown): string[] => {
  const result: string[] = [];
  const seen = new Set<string>();

  const push = (candidate: Record<string, unknown>) => {
    const normalized = normalizeImageValue(candidate);
    if (normalized && !seen.has(normalized)) {
      seen.add(normalized);
      result.push(normalized);
    }
  };

  const walk = (payload: Record<string, unknown>) => {
    push(payload);
    if (Array.isArray(payload)) {
      payload.forEach((item) => walk(item));
      return;
    }
    if (isPlainObject(payload)) {
      Object.values(payload).forEach((item) => walk(item));
    }
  };

  walk(value);
  return result;
};

const extractMediaUrls = (
  value: unknown,
  isLikelyMediaUrl: (candidate: string) => boolean,
  mediaKind: 'audio' | 'video'
): string[] => {
  const result: string[] = [];
  const seen = new Set<string>();
  const sourceHints = new Set([
    `source${mediaKind}url`,
    `source_${mediaKind}_url`,
    `reference${mediaKind}url`,
    `reference_${mediaKind}_url`,
    `input${mediaKind}url`,
    `input_${mediaKind}_url`,
    `original${mediaKind}url`,
    `original_${mediaKind}_url`,
    `start${mediaKind}url`,
    `start_${mediaKind}_url`,
    'raw',
    'rawurl',
    'raw_url',
    'dataurl',
    'data_url',
  ]);
  if (mediaKind === 'video') {
    sourceHints.add('provider_file_name');
    sourceHints.add('providerfilename');
    sourceHints.add('provider_file_uri');
    sourceHints.add('providerfileuri');
    sourceHints.add('gcs_uri');
    sourceHints.add('gcsuri');
    sourceHints.add('file_uri');
    sourceHints.add('fileuri');
    sourceHints.add('google_file_uri');
    sourceHints.add('googlefileuri');
  }
  const sourceContainerHints = new Set([
    `reference${mediaKind}s`,
    `reference_${mediaKind}s`,
    `reference${mediaKind}`,
    `reference_${mediaKind}`,
    `source${mediaKind}s`,
    `source_${mediaKind}s`,
    `source${mediaKind}`,
    `source_${mediaKind}`,
    'source',
    'source_input',
    'sourceinput',
    'original',
    `original${mediaKind}`,
    `original_${mediaKind}`,
    'input',
    'inputs',
  ]);

  const push = (candidate: unknown, keyHint = '', mimeType = '') => {
    if (typeof candidate !== 'string') return;
    const normalized = candidate.trim();
    if (!normalized || seen.has(normalized)) {
      return;
    }
    const normalizedKeyHint = String(keyHint || '').trim().toLowerCase().replace(/-/g, '_');
    if (sourceHints.has(normalizedKeyHint)) {
      return;
    }
    const normalizedMimeType = String(mimeType || '').trim().toLowerCase();
    const isMediaTempAttachment =
      isTempAttachmentUrl(normalized)
      && (
        normalizedMimeType.startsWith(`${mediaKind}/`)
        || normalizedKeyHint.includes(mediaKind)
      );
    if (!isLikelyMediaUrl(normalized) && !isMediaTempAttachment) {
      return;
    }
    seen.add(normalized);
    result.push(normalized);
  };

  const walk = (payload: unknown, keyHint = '', parentMimeType = '') => {
    push(payload, keyHint, parentMimeType);
    if (Array.isArray(payload)) {
      payload.forEach((item) => walk(item, keyHint, parentMimeType));
      return;
    }
    if (isPlainObject(payload)) {
      const objectMimeType = inferMediaMimeType(payload) || parentMimeType;
      Object.entries(payload).forEach(([key, item]) => {
        const normalizedKey = String(key || '').trim().toLowerCase().replace(/-/g, '_');
        if (sourceContainerHints.has(normalizedKey)) {
          return;
        }
        walk(item, key, objectMimeType);
      });
    }
  };

  walk(value);
  return result;
};

export const extractAudioUrls = (value: unknown): string[] => extractMediaUrls(value, isLikelyAudioUrl, 'audio');

export const extractVideoUrls = (value: unknown): string[] => extractMediaUrls(value, isLikelyVideoUrl, 'video');

const normalizeDisplayUrlValue = (value: unknown): string | null => {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  if (!trimmed) return null;
  if (trimmed.startsWith('data:image/')) return null;
  if (
    /^(https?:\/\/|blob:|oss:\/\/|file:\/\/)/i.test(trimmed)
    || trimmed.startsWith('/')
    || isLocalFilesystemPath(trimmed)
  ) {
    return trimmed;
  }
  return null;
};

export const extractUrlContent = (value: unknown): string[] => {
  const result: string[] = [];
  const seen = new Set<string>();

  const push = (candidate: Record<string, unknown>) => {
    const normalized = normalizeDisplayUrlValue(candidate);
    if (!normalized || seen.has(normalized)) {
      return;
    }
    seen.add(normalized);
    result.push(normalized);
  };

  const walk = (payload: unknown, depth = 0) => {
    if (depth > 12) return;
    push(payload);
    if (Array.isArray(payload)) {
      payload.forEach((item) => walk(item, depth + 1));
      return;
    }
    if (isPlainObject(payload)) {
      Object.values(payload).forEach((item) => walk(item, depth + 1));
    }
  };

  walk(value);
  return result;
};

const normalizeThoughtEntryText = (value: unknown): string => {
  if (value == null) return '';
  if (typeof value === 'string') {
    return stripMarkdownCodeFence(value).trim();
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  if (Array.isArray(value)) {
    return value
      .map((item) => normalizeThoughtEntryText(item))
      .filter(Boolean)
      .join('\n')
      .trim();
  }
  if (isPlainObject(value)) {
    const keys = ['text', 'summary', 'content', 'message', 'thought', 'reasoning', 'thinking'];
    for (const key of keys) {
      const candidate = value[key];
      const normalized = normalizeThoughtEntryText(candidate);
      if (normalized) return normalized;
    }
    try {
      return JSON.stringify(value, null, 2);
    } catch {
      return String(value);
    }
  }
  return String(value);
};

export const extractThoughtContent = (value: unknown): string[] => {
  const result: string[] = [];
  const seen = new Set<string>();
  const thoughtKeys = new Set([
    'thoughts',
    'thoughtsummary',
    'thought_summary',
    'reasoning',
    'thinking',
    'textresponse',
    'text_response',
  ]);

  const push = (candidate: Record<string, unknown>) => {
    const normalized = normalizeThoughtEntryText(candidate);
    if (!normalized) return;
    const compact = normalized.replace(/\s+/g, ' ').trim();
    if (!compact) return;
    const key = compact.slice(0, 240);
    if (seen.has(key)) return;
    seen.add(key);
    result.push(normalized.length > 1200 ? `${normalized.slice(0, 1200)}\n...(内容已截断)` : normalized);
  };

  const walk = (payload: unknown, depth = 0) => {
    if (depth > 12 || payload == null) return;
    if (Array.isArray(payload)) {
      payload.forEach((item) => walk(item, depth + 1));
      return;
    }
    if (!isPlainObject(payload)) {
      return;
    }

    Object.entries(payload).forEach(([key, item]) => {
      const normalizedKey = String(key || '').trim().toLowerCase().replace(/-/g, '_');
      if (thoughtKeys.has(normalizedKey)) {
        if (Array.isArray(item)) {
          item.forEach((entry) => push(entry));
        } else {
          push(item);
        }
      }
      walk(item, depth + 1);
    });
  };

  walk(value);
  return result;
};

export const extractTextContent = (value: unknown): string => {
  if (typeof value === 'string') {
    const normalized = stripMarkdownCodeFence(value);
    if (!normalized) return '';
    const trimmed = normalized.trim();
    if ((trimmed.startsWith('{') && trimmed.endsWith('}')) || (trimmed.startsWith('[') && trimmed.endsWith(']'))) {
      try {
        const parsed = JSON.parse(trimmed);
        return extractTextContent(parsed);
      } catch {
        // not JSON payload, fallback to plain string
      }
    }
    if (
      trimmed.startsWith('data:image/')
      || trimmed.startsWith('data:audio/')
      || trimmed.startsWith('data:video/')
    ) return '';
    if (trimmed.replace(/\s+/g, '').length >= 128 && /^[A-Za-z0-9+/=]+$/.test(trimmed.replace(/\s+/g, ''))) return '';
    return normalized;
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value);
  }
  if (Array.isArray(value)) {
    return value.map((item) => extractTextContent(item)).filter(Boolean).join('\n');
  }
  if (isPlainObject(value)) {
    const candidates = ['text', 'message', 'summary', 'content', 'result', 'finalOutput', 'merged'];
    for (const key of candidates) {
      const candidate = value[key];
      if (typeof candidate === 'string' && candidate.trim()) {
        const normalizedCandidate = candidate.trim();
        if (
          normalizedCandidate.startsWith('data:image/')
          || normalizedCandidate.startsWith('data:audio/')
          || normalizedCandidate.startsWith('data:video/')
        ) continue;
        return stripMarkdownCodeFence(candidate);
      }
      const nested = extractTextContent(candidate);
      if (nested) return nested;
    }
  }
  return '';
};

export const parseDataUrlBlob = (dataUrl: string): Blob | null => {
  const match = /^data:([^;,]+)?(?:;base64)?,(.*)$/i.exec(dataUrl);
  if (!match) return null;
  const mimeType = (match[1] || 'application/octet-stream').trim();
  const payload = match[2] || '';
  const isBase64 = /;base64,/i.test(dataUrl);
  try {
    if (isBase64) {
      const binary = atob(payload);
      const bytes = new Uint8Array(binary.length);
      for (let i = 0; i < binary.length; i += 1) {
        bytes[i] = binary.charCodeAt(i);
      }
      return new Blob([bytes], { type: mimeType });
    }
    return new Blob([decodeURIComponent(payload)], { type: mimeType });
  } catch {
    return null;
  }
};

const inferImageExtFromMime = (mimeType: string): string => {
  const normalized = (mimeType || '').toLowerCase();
  if (normalized.includes('png')) return 'png';
  if (normalized.includes('jpeg') || normalized.includes('jpg')) return 'jpg';
  if (normalized.includes('webp')) return 'webp';
  if (normalized.includes('gif')) return 'gif';
  if (normalized.includes('bmp')) return 'bmp';
  if (normalized.includes('svg')) return 'svg';
  return 'png';
};

export const inferImageExtFromUrl = (imageUrl: string, fallbackMime = ''): string => {
  if (imageUrl.startsWith('data:image/')) {
    const mime = imageUrl.slice(5, imageUrl.indexOf(';') > 0 ? imageUrl.indexOf(';') : imageUrl.indexOf(','));
    return inferImageExtFromMime(mime);
  }
  const pathname = imageUrl.toLowerCase().split('?')[0].split('#')[0];
  if (pathname.endsWith('.jpeg') || pathname.endsWith('.jpg')) return 'jpg';
  if (pathname.endsWith('.webp')) return 'webp';
  if (pathname.endsWith('.gif')) return 'gif';
  if (pathname.endsWith('.bmp')) return 'bmp';
  if (pathname.endsWith('.svg')) return 'svg';
  if (pathname.endsWith('.png')) return 'png';
  if (fallbackMime) return inferImageExtFromMime(fallbackMime);
  return 'png';
};

const mergeUniqueNormalizedUrls = (base: string[], extra: string[], limit: number) => {
  const seen = new Set<string>();
  const merged: string[] = [];
  [...base, ...extra].forEach((item) => {
    const normalized = String(item || '').trim();
    if (!normalized || seen.has(normalized)) return;
    seen.add(normalized);
    merged.push(normalized);
  });
  return merged.slice(0, limit);
};

export const mergePreviewImagesIntoResult = (payload: unknown, previewImages: string[]) => {
  const normalizedPreviewImages = Array.isArray(previewImages)
    ? previewImages.map((item) => String(item || '').trim()).filter(Boolean).slice(0, PREVIEW_IMAGE_MAX_ENTRIES)
    : [];
  if (normalizedPreviewImages.length === 0) {
    return payload;
  }

  const extractedImageUrls = extractImageUrls(payload);
  const mergedImageUrls = mergeUniqueNormalizedUrls(extractedImageUrls, normalizedPreviewImages, PREVIEW_IMAGE_MAX_ENTRIES);
  const firstRenderableImage = mergedImageUrls.find((imageUrl) => isDirectlyRenderableImageUrl(imageUrl)) || '';
  const firstPreviewImage = normalizedPreviewImages[0];

  if (isPlainObject(payload)) {
    const currentImageUrls = Array.isArray(payload.imageUrls)
      ? payload.imageUrls.map((item: Record<string, unknown>) => String(item || '').trim()).filter(Boolean)
      : [];
    const mergedObjectImageUrls = mergeUniqueNormalizedUrls(currentImageUrls, mergedImageUrls, PREVIEW_IMAGE_MAX_ENTRIES);
    const payloadImageUrl = typeof payload.imageUrl === 'string' ? payload.imageUrl.trim() : '';
    return {
      ...payload,
      imageUrl: payloadImageUrl || firstRenderableImage || firstPreviewImage,
      imageUrls: mergedObjectImageUrls.length > 0 ? mergedObjectImageUrls : mergedImageUrls,
    };
  }

  return {
    imageUrl: firstRenderableImage || firstPreviewImage,
    imageUrls: mergedImageUrls.length > 0 ? mergedImageUrls : normalizedPreviewImages,
    text: extractTextContent(payload),
  };
};

type PreviewMediaKind = 'audio' | 'video';

export const mergePreviewMediaIntoResult = (
  payload: unknown,
  mediaKind: PreviewMediaKind,
  previewUrls: string[],
) => {
  const normalizedPreviewUrls = Array.isArray(previewUrls)
    ? previewUrls.map((item) => String(item || '').trim()).filter(Boolean).slice(0, PREVIEW_IMAGE_MAX_ENTRIES)
    : [];
  if (normalizedPreviewUrls.length === 0) {
    return payload;
  }

  const isAudio = mediaKind === 'audio';
  const urlKey = isAudio ? 'audioUrl' : 'videoUrl';
  const urlsKey = isAudio ? 'audioUrls' : 'videoUrls';
  const extractUrls = isAudio ? extractAudioUrls : extractVideoUrls;
  const isRenderableUrl = isAudio ? isDirectlyRenderableAudioUrl : isDirectlyRenderableVideoUrl;
  const extractedMediaUrls = extractUrls(payload);
  const mergedMediaUrls = mergeUniqueNormalizedUrls(extractedMediaUrls, normalizedPreviewUrls, PREVIEW_IMAGE_MAX_ENTRIES);
  const firstRenderableMediaUrl = mergedMediaUrls.find((item) => isRenderableUrl(item)) || normalizedPreviewUrls[0] || '';

  if (isPlainObject(payload)) {
    const currentMediaUrls = Array.isArray(payload[urlsKey])
      ? payload[urlsKey].map((item: Record<string, unknown>) => String(item || '').trim()).filter(Boolean)
      : [];
    const mergedObjectMediaUrls = mergeUniqueNormalizedUrls(currentMediaUrls, mergedMediaUrls, PREVIEW_IMAGE_MAX_ENTRIES);
    const payloadMediaUrl = typeof payload[urlKey] === 'string' ? payload[urlKey].trim() : '';
    return {
      ...payload,
      [urlKey]: payloadMediaUrl || firstRenderableMediaUrl,
      [urlsKey]: mergedObjectMediaUrls.length > 0 ? mergedObjectMediaUrls : mergedMediaUrls,
    };
  }

  return {
    [urlKey]: firstRenderableMediaUrl,
    [urlsKey]: mergedMediaUrls.length > 0 ? mergedMediaUrls : normalizedPreviewUrls,
    text: extractTextContent(payload),
  };
};
