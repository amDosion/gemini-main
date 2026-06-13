import React from 'react';
import { Attachment } from '../../types/types';
import { Download, Maximize2, FileText, Music, Video as VideoIcon, Edit, File } from 'lucide-react';
import { CachedImage } from '../common/CachedImage';
import { RetainedAudio, RetainedVideo } from '../common/RetainedMedia';
import { getPreferredAttachmentUrl, getRenderableAttachmentUrl } from '../../utils/attachmentUrl';
import { downloadSourceUrlInBrowser } from '../../services/downloadService';

interface AttachmentGridProps {
  attachments: Attachment[];
  onImageClick?: (url: string) => void;
  onEditImage?: (url: string, attachment?: Attachment) => void;
}

const getAttachmentKey = (attachment: Attachment): string => {
  const segments = [
    attachment.id,
    attachment.url,
    attachment.tempUrl,
    attachment.cloudUrl,
    attachment.fileUri,
    attachment.name,
    attachment.mimeType,
  ].filter((segment): segment is string => Boolean(segment && segment.length > 0));

  return segments.join('|');
};

export const AttachmentGrid: React.FC<AttachmentGridProps> = ({
  attachments,
  onImageClick,
  onEditImage,
}) => {
  if (!attachments || attachments.length === 0) return null;

  const handleDownload = (e: React.MouseEvent, url: string, name: string) => {
    e.preventDefault();
    e.stopPropagation();
    void downloadSourceUrlInBrowser({
      sourceUrl: url,
      fileName: name || `gemini-file-${Date.now()}`,
    }).catch((error) => {
      console.warn('[AttachmentGrid] Download blocked or failed:', error);
    });
  };

  const getDisplayUrl = (attachment: Attachment): string | null => {
    return getRenderableAttachmentUrl(attachment);
  };

  const getDownloadUrl = (attachment: Attachment): string | null => {
    return getPreferredAttachmentUrl(attachment);
  };

  const handleEdit = (e: React.MouseEvent, url: string, attachment?: Attachment) => {
    e.stopPropagation();
    onEditImage?.(url, attachment);
  };

  // Specialized Layouts
  const isSingleVideo = attachments.length === 1 && attachments[0].mimeType.startsWith('video/');
  const isSingleImage = attachments.length === 1 && attachments[0].mimeType.startsWith('image/');
  const isSingleAudio = attachments.length === 1 && attachments[0].mimeType.startsWith('audio/');

  // 1. Single Video (Hero Layout)
  if (isSingleVideo) {
    const att = attachments[0];
    const url = getDisplayUrl(att);
    if (!url) return null;

    return (
      <div className="mt-3 rounded-xl overflow-hidden border border-slate-600/50 shadow-2xl bg-black max-w-full">
        <RetainedVideo src={url} controls className="w-full max-h-[180px]" autoPlay muted />
        <div className="p-2 bg-slate-900/80 flex items-center justify-between text-xs text-slate-400 px-3">
          <span className="flex items-center gap-1">
            <VideoIcon size={12} /> Generated Video
          </span>
          <button
            onClick={(e) => handleDownload(e, url, att.name)}
            className="hover:text-white flex items-center gap-1"
          >
            <Download size={12} /> Download
          </button>
        </div>
      </div>
    );
  }

  // 2. Single Audio (Player Layout)
  if (isSingleAudio) {
    const att = attachments[0];
    const url = getDisplayUrl(att);
    if (!url) return null;

    return (
      <div className="mt-2 p-4 rounded-xl border border-slate-600/50 shadow-lg bg-slate-900/80 flex items-center gap-4">
        <div className="p-3 rounded-full bg-slate-800 text-cyan-400 border border-slate-700 shadow-inner">
          <Music size={24} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-medium text-slate-200 mb-1">Generated Audio</div>
          <RetainedAudio src={url} controls className="h-8 w-full" />
        </div>
        <button
          onClick={(e) => handleDownload(e, url, att.name)}
          className="p-2 hover:bg-slate-800 rounded-full text-slate-400 hover:text-white transition-colors"
        >
          <Download size={18} />
        </button>
      </div>
    );
  }

  // 3. Grid Layout (Images & Files)
  const columns = Math.min(attachments.length, 4);
  const gridStyle: React.CSSProperties = {
    gridTemplateColumns: `repeat(${columns}, 96px)`,
    width: 'fit-content',
    maxWidth: 'calc(96px * 4 + 0.5rem * 3)',
  };

  return (
    <div className="grid justify-items-start gap-2 mt-2" style={gridStyle}>
      {attachments.map((att) => {
        const attachmentKey = getAttachmentKey(att);
        const isImage = att.mimeType.startsWith('image/');
        const isVideo = att.mimeType.startsWith('video/');
        const isAudio = att.mimeType.startsWith('audio/');
        const isPdf = att.mimeType.includes('pdf');
        if (isImage) {
          const url = getDisplayUrl(att);
          if (!url) return null;

          return (
            <div
              key={attachmentKey}
              className="flex flex-col rounded-lg overflow-hidden border border-slate-700/60 shadow-md bg-slate-900/80 w-[96px]"
            >
              <div
                className="relative group/img w-full h-[64px] bg-slate-900 cursor-pointer"
                onClick={() => onImageClick?.(url)}
                title="Preview"
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onImageClick?.(url);
                  }
                }}
              >
                <CachedImage
                  src={url}
                  source={{
                    ...att,
                    attachmentId: att.id,
                    url,
                    mimeType: att.mimeType,
                    name: att.name,
                  }}
                  alt={att.name}
                  className="w-full h-full object-cover transition-transform duration-300 group-hover/img:scale-105"
                />
                <div className="absolute inset-0 bg-black/40 opacity-0 group-hover/img:opacity-100 transition-opacity flex items-center justify-center gap-2">
                  <button
                    onClick={(e) => handleDownload(e, url, att.name)}
                    className="p-1.5 bg-white/10 hover:bg-white/20 text-white rounded-full border border-white/20"
                    title="Download"
                  >
                    <Download size={14} />
                  </button>
                  <button
                    onClick={() => onImageClick?.(url)}
                    className="p-1.5 bg-white/10 hover:bg-white/20 text-white rounded-full border border-white/20"
                    title="Fullscreen"
                  >
                    <Maximize2 size={14} />
                  </button>
                  {onEditImage && (
                    <button
                      onClick={(e) => handleEdit(e, url, att)}
                      className="p-1.5 bg-pink-500/80 hover:bg-pink-500 text-white rounded-full border border-white/20"
                      title="Edit this image"
                    >
                      <Edit size={14} />
                    </button>
                  )}
                </div>
              </div>
            </div>
          );
        } else if (isVideo) {
          const url = getDisplayUrl(att);
          if (!url) return null;

          return (
            <div
              key={attachmentKey}
              className="flex flex-col rounded-lg overflow-hidden border border-slate-700/60 shadow-md bg-slate-900/80 w-[96px]"
            >
              <div className="w-full h-[64px] bg-black">
                <RetainedVideo src={url} controls className="w-full h-full object-cover" />
              </div>
            </div>
          );
        } else if (isAudio) {
          const url = getDisplayUrl(att);
          if (!url) return null;

          return (
            <div
              key={attachmentKey}
              className="flex flex-col rounded-lg overflow-hidden border border-slate-700/60 shadow-md bg-slate-900/80 w-[96px]"
            >
              <div className="flex items-center gap-2 px-2 py-2">
                <div className="p-1.5 rounded-full bg-slate-800 text-yellow-400">
                  <Music size={14} />
                </div>
              </div>
              <div className="px-2 pb-2">
                <RetainedAudio src={url} controls className="h-6 w-full" />
              </div>
            </div>
          );
        } else {
          // PDF & Generic Files
          const url = getDownloadUrl(att);
          if (!url) return null;

          return (
            <button
              type="button"
              key={attachmentKey}
              onClick={(e) => handleDownload(e, url, att.name)}
              className="flex flex-col rounded-lg overflow-hidden border border-slate-700/60 shadow-md bg-slate-900/80 hover:bg-slate-800 transition-all hover:border-slate-500 w-[96px]"
            >
              <div
                className={`flex items-center gap-2 px-2 py-2 ${isPdf ? 'text-red-400' : 'text-blue-400'}`}
              >
                {isPdf ? <FileText size={14} /> : <File size={14} />}
                <span className="text-xs uppercase text-slate-400">
                  {att.mimeType.split('/')[1] || 'FILE'}
                </span>
              </div>
            </button>
          );
        }
      })}
    </div>
  );
};
