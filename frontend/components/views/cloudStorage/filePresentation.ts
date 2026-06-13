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

const IMAGE_EXTENSIONS = new Set([
  'jpg',
  'jpeg',
  'png',
  'gif',
  'webp',
  'bmp',
  'svg',
  'avif',
  'heic',
  'heif',
  'tif',
  'tiff',
]);
const VIDEO_EXTENSIONS = new Set([
  'mp4',
  'mov',
  'avi',
  'mkv',
  'webm',
  'm4v',
  'wmv',
  'flv',
  'ts',
  'm2ts',
]);
const SPREADSHEET_EXTENSIONS = new Set(['xls', 'xlsx', 'csv', 'tsv', 'ods']);
const DOCUMENT_EXTENSIONS = new Set(['doc', 'docx', 'txt', 'rtf', 'odt', 'ppt', 'pptx', 'md']);
const RAW_EXTENSIONS = new Set([
  'raw',
  'arw',
  'cr2',
  'cr3',
  'nef',
  'dng',
  'rw2',
  'orf',
  'raf',
  'srw',
]);
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

export const getGeneratedThumbPresentation = (
  kind: FileKind,
  ext: string
): { bg: string; fg: string; label: string } => {
  const label =
    (ext || kind)
      .replace(/[^a-zA-Z0-9]/g, '')
      .toUpperCase()
      .slice(0, 4) || 'FILE';
  return { ...getKindPalette(kind), label };
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
