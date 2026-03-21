import { StorageBrowseItem } from '../../../types/storage';

export type FileKind =
  | 'directory'
  | 'image'
  | 'video'
  | 'spreadsheet'
  | 'document'
  | 'raw'
  | 'design'
  | 'pdf'
  | 'archive'
  | 'other';

const IMAGE_EXTENSIONS = new Set(['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg', 'avif', 'heic', 'heif', 'tif', 'tiff']);
const VIDEO_EXTENSIONS = new Set(['mp4', 'mov', 'avi', 'mkv', 'webm', 'm4v', 'wmv', 'flv', 'ts', 'm2ts']);
const SPREADSHEET_EXTENSIONS = new Set(['xls', 'xlsx', 'csv', 'tsv', 'ods']);
const DOCUMENT_EXTENSIONS = new Set(['doc', 'docx', 'txt', 'rtf', 'odt', 'ppt', 'pptx', 'md']);
const RAW_EXTENSIONS = new Set(['raw', 'arw', 'cr2', 'cr3', 'nef', 'dng', 'rw2', 'orf', 'raf', 'srw']);
const DESIGN_EXTENSIONS = new Set(['psd', 'psb', 'ai', 'sketch', 'xd']);
const PDF_EXTENSIONS = new Set(['pdf']);
const ARCHIVE_EXTENSIONS = new Set(['zip', 'rar', '7z', 'tar', 'gz', 'tgz', 'bz2']);

export const getFileExtension = (name: string): string => {
  const index = name.lastIndexOf('.');
  if (index < 0 || index === name.length - 1) return '';
  return name.slice(index + 1).toLowerCase();
};

export const getFileKind = (item: StorageBrowseItem): FileKind => {
  if (item.entryType === 'directory') return 'directory';
  const ext = getFileExtension(item.name);
  if (IMAGE_EXTENSIONS.has(ext)) return 'image';
  if (VIDEO_EXTENSIONS.has(ext)) return 'video';
  if (SPREADSHEET_EXTENSIONS.has(ext)) return 'spreadsheet';
  if (DOCUMENT_EXTENSIONS.has(ext)) return 'document';
  if (RAW_EXTENSIONS.has(ext)) return 'raw';
  if (DESIGN_EXTENSIONS.has(ext)) return 'design';
  if (PDF_EXTENSIONS.has(ext)) return 'pdf';
  if (ARCHIVE_EXTENSIONS.has(ext)) return 'archive';
  return 'other';
};

const getKindPalette = (kind: FileKind): { bg: string; fg: string } => {
  switch (kind) {
    case 'spreadsheet':
      return { bg: '#0f5132', fg: '#b6f5cf' };
    case 'document':
      return { bg: '#1f3a8a', fg: '#dbeafe' };
    case 'raw':
      return { bg: '#5b21b6', fg: '#ede9fe' };
    case 'design':
      return { bg: '#9d174d', fg: '#fce7f3' };
    case 'video':
      return { bg: '#7c2d12', fg: '#ffedd5' };
    case 'pdf':
      return { bg: '#991b1b', fg: '#fee2e2' };
    case 'archive':
      return { bg: '#3f3f46', fg: '#f4f4f5' };
    case 'image':
      return { bg: '#065f46', fg: '#d1fae5' };
    default:
      return { bg: '#334155', fg: '#e2e8f0' };
  }
};

export const createGeneratedThumb = (kind: FileKind, ext: string): string => {
  const safeLabel = (ext || kind || 'file').replace(/[^a-zA-Z0-9]/g, '').toUpperCase().slice(0, 4) || 'FILE';
  const palette = getKindPalette(kind);
  const svg = `
<svg xmlns="http://www.w3.org/2000/svg" width="88" height="88" viewBox="0 0 88 88">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="${palette.bg}"/>
      <stop offset="100%" stop-color="#0f172a"/>
    </linearGradient>
  </defs>
  <rect x="2" y="2" width="84" height="84" rx="14" fill="url(#g)" stroke="#1e293b" stroke-width="2"/>
  <text x="44" y="49" text-anchor="middle" dominant-baseline="middle" font-size="18" font-family="Arial, sans-serif" font-weight="700" fill="${palette.fg}">${safeLabel}</text>
</svg>`;
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
};

export const formatBytes = (bytes?: number | null): string => {
  if (bytes === null || bytes === undefined || Number.isNaN(bytes)) return '-';
  if (bytes === 0) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const base = Math.floor(Math.log(bytes) / Math.log(1024));
  const unitIndex = Math.min(base, units.length - 1);
  const value = bytes / Math.pow(1024, unitIndex);
  return `${value.toFixed(value >= 100 || unitIndex === 0 ? 0 : 1)} ${units[unitIndex]}`;
};

export const formatDate = (value?: string | null): string => {
  if (!value) return '-';
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return value;
  return dt.toLocaleString('zh-CN', { hour12: false });
};

export const providerLabel = (provider: string): string => {
  switch (provider) {
    case 'aliyun-oss':
      return 'Aliyun OSS';
    case 'tencent-cos':
      return 'Tencent COS';
    case 'google-drive':
      return 'Google Drive';
    case 's3-compatible':
      return 'S3 Compatible';
    case 'local':
      return 'Local';
    case 'lsky':
      return 'Lsky';
    default:
      return provider;
  }
};
