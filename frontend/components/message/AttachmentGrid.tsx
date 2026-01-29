
import React from 'react';
import { Attachment } from '../../types/types';
import { Download, Maximize2, FileText, Music, Video as VideoIcon, Edit, Crop, File } from 'lucide-react';

interface AttachmentGridProps {
  attachments: Attachment[];
  onImageClick?: (url: string) => void;
  onEditImage?: (url: string, attachment?: Attachment) => void;
}

export const AttachmentGrid: React.FC<AttachmentGridProps> = ({ attachments, onImageClick, onEditImage }) => {
  if (!attachments || attachments.length === 0) return null;

  const handleDownload = (e: React.MouseEvent, url: string, name: string) => {
    e.stopPropagation();
    const link = document.createElement('a');
    link.href = url;
    link.download = name || `gemini-file-${Date.now()}`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
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
      const url = att.url || att.fileUri;
      if (!url) return null;
      
      return (
        <div className="mt-3 rounded-xl overflow-hidden border border-slate-600/50 shadow-2xl bg-black max-w-full">
            <video src={url} controls className="w-full max-h-[180px]" autoPlay muted />
            <div className="p-2 bg-slate-900/80 flex items-center justify-between text-xs text-slate-400 px-3">
                <span className="flex items-center gap-1"><VideoIcon size={12}/> Generated Video</span>
                <button onClick={(e) => handleDownload(e, url, att.name)} className="hover:text-white flex items-center gap-1">
                    <Download size={12}/> Download
                </button>
            </div>
        </div>
      );
  }

  // 2. Single Audio (Player Layout)
  if (isSingleAudio) {
      const att = attachments[0];
      const url = att.url || att.fileUri;
      if (!url) return null;

      return (
        <div className="mt-2 p-4 rounded-xl border border-slate-600/50 shadow-lg bg-slate-900/80 flex items-center gap-4">
            <div className="p-3 rounded-full bg-slate-800 text-cyan-400 border border-slate-700 shadow-inner">
                <Music size={24} />
            </div>
            <div className="flex-1 min-w-0">
                 <div className="text-sm font-medium text-slate-200 mb-1">Generated Audio</div>
                 <audio src={url} controls className="h-8 w-full" />
            </div>
            <button onClick={(e) => handleDownload(e, url, att.name)} className="p-2 hover:bg-slate-800 rounded-full text-slate-400 hover:text-white transition-colors">
                <Download size={18}/>
            </button>
        </div>
      );
  }

  // 3. Grid Layout (Images & Files)
  const columns = Math.min(attachments.length, 4);
  const gridStyle: React.CSSProperties = {
    gridTemplateColumns: `repeat(${columns}, 96px)`,
    width: 'fit-content',
    maxWidth: 'calc(96px * 4 + 0.5rem * 3)'
  };

  return (
    <div
      className="grid justify-items-start gap-2 mt-2"
      style={gridStyle}
    >
      {attachments.map((att, idx) => {
        const isImage = att.mimeType.startsWith('image/');
        const isVideo = att.mimeType.startsWith('video/');
        const isAudio = att.mimeType.startsWith('audio/');
        const isPdf = att.mimeType.includes('pdf');
        const url = att.url || att.fileUri;

        if (!url) return null;

        if (isImage) {
            // ✅ 修复：使用 URL 优先级降级策略（url -> tempUrl -> fileUri）
            const displayUrl = att.url || att.tempUrl || att.fileUri;
            if (!displayUrl) return null;
            
            return (
                <div key={idx} className="flex flex-col rounded-lg overflow-hidden border border-slate-700/60 shadow-md bg-slate-900/80 w-[96px]">
                    <div
                      className="relative group/img w-full h-[64px] bg-slate-900 cursor-pointer"
                      onClick={() => onImageClick?.(displayUrl)}
                      title="Preview"
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          onImageClick?.(displayUrl);
                        }
                      }}
                    >
                      <img
                        src={displayUrl}
                        alt={att.name}
                        className="w-full h-full object-cover transition-transform duration-300 group-hover/img:scale-105"
                      />
                      <div className="absolute inset-0 bg-black/40 opacity-0 group-hover/img:opacity-100 transition-opacity flex items-center justify-center gap-2">
                        <button
                          onClick={(e) => handleDownload(e, displayUrl, att.name)}
                          className="p-1.5 bg-white/10 hover:bg-white/20 text-white rounded-full border border-white/20"
                          title="Download"
                        >
                          <Download size={14} />
                        </button>
                        <button
                          onClick={() => onImageClick?.(displayUrl)}
                          className="p-1.5 bg-white/10 hover:bg-white/20 text-white rounded-full border border-white/20"
                          title="Fullscreen"
                        >
                          <Maximize2 size={14} />
                        </button>
                        {onEditImage && (
                          <button
                            onClick={(e) => handleEdit(e, displayUrl, att)}
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
            // ✅ 修复：视频也使用 URL 优先级降级策略
            const displayUrl = att.url || att.tempUrl || att.fileUri;
            if (!displayUrl) return null;
            
            return (
                <div key={idx} className="flex flex-col rounded-lg overflow-hidden border border-slate-700/60 shadow-md bg-slate-900/80 w-[96px]">
                    <div className="w-full h-[64px] bg-black">
                      <video src={displayUrl} controls className="w-full h-full object-cover" />
                    </div>
                </div>
            );
        } else if (isAudio) {
            // ✅ 修复：音频也使用 URL 优先级降级策略
            const displayUrl = att.url || att.tempUrl || att.fileUri;
            if (!displayUrl) return null;
            
             return (
                <div key={idx} className="flex flex-col rounded-lg overflow-hidden border border-slate-700/60 shadow-md bg-slate-900/80 w-[96px]">
                    <div className="flex items-center gap-2 px-2 py-2">
                      <div className="p-1.5 rounded-full bg-slate-800 text-yellow-400"><Music size={14} /></div>
                    </div>
                    <div className="px-2 pb-2">
                      <audio src={displayUrl} controls className="h-6 w-full" />
                    </div>
                </div>
            );
        } else {
            // PDF & Generic Files
            return (
                <a key={idx} href={url} download={att.name} className="flex flex-col rounded-lg overflow-hidden border border-slate-700/60 shadow-md bg-slate-900/80 hover:bg-slate-800 transition-all hover:border-slate-500 w-[96px]">
                    <div className={`flex items-center gap-2 px-2 py-2 ${isPdf ? 'text-red-400' : 'text-blue-400'}`}>
                        {isPdf ? <FileText size={14} /> : <File size={14} />}
                        <span className="text-xs uppercase text-slate-400">{att.mimeType.split('/')[1] || 'FILE'}</span>
                    </div>
                </a>
            );
        }
      })}
    </div>
  );
};
