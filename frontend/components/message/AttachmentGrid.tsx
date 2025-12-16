
import React from 'react';
import { Attachment } from '../../../types';
import { Download, Maximize2, FileText, Music, Video as VideoIcon, Edit, Crop, File } from 'lucide-react';

interface AttachmentGridProps {
  attachments: Attachment[];
  onImageClick?: (url: string) => void;
  onEditImage?: (url: string) => void;
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

  const handleEdit = (e: React.MouseEvent, url: string) => {
      e.stopPropagation();
      onEditImage?.(url);
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
            <video src={url} controls className="w-full max-h-[500px]" autoPlay muted />
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
  return (
    <div className={`grid gap-3 mt-2 ${isSingleImage ? 'grid-cols-1 max-w-md' : 'grid-cols-1 sm:grid-cols-2'}`}>
      {attachments.map((att, idx) => {
        const isImage = att.mimeType.startsWith('image/');
        const isVideo = att.mimeType.startsWith('video/');
        const isAudio = att.mimeType.startsWith('audio/');
        const isPdf = att.mimeType.includes('pdf');
        const url = att.url || att.fileUri;

        if (!url) return null;

        if (isImage) {
            return (
                <div key={idx} className="relative rounded-xl overflow-hidden border border-slate-600/50 shadow-lg group/img aspect-square bg-slate-900">
                    <img 
                       src={url} 
                       alt={att.name}
                       className="w-full h-full object-cover transition-transform duration-500 group-hover/img:scale-105 cursor-pointer" 
                       onClick={() => onImageClick?.(url)}
                    />
                    <div className="absolute inset-0 bg-black/40 opacity-0 group-hover/img:opacity-100 transition-opacity flex items-center justify-center gap-3 backdrop-blur-[2px]">
                       <button 
                           onClick={(e) => handleDownload(e, url, att.name)} 
                           className="p-2 bg-white/10 hover:bg-white/20 text-white rounded-full backdrop-blur-md border border-white/20 transition-transform hover:scale-110"
                           title="Download"
                        >
                           <Download size={20} />
                       </button>
                       <button 
                           onClick={() => onImageClick?.(url)} 
                           className="p-2 bg-white/10 hover:bg-white/20 text-white rounded-full backdrop-blur-md border border-white/20 transition-transform hover:scale-110"
                           title="Fullscreen"
                        >
                           <Maximize2 size={20} />
                       </button>
                       {onEditImage && (
                        <button 
                            onClick={(e) => handleEdit(e, url)} 
                            className="p-2 bg-pink-500/80 hover:bg-pink-500 text-white rounded-full backdrop-blur-md border border-white/20 transition-transform hover:scale-110"
                            title="Edit this image"
                        >
                            <Edit size={20} />
                        </button>
                       )}
                    </div>
                </div>
            );
        } else if (isVideo) {
            return (
                <div key={idx} className="rounded-xl overflow-hidden border border-slate-600/50 shadow-lg bg-black">
                    <video src={url} controls className="w-full max-h-[200px]" />
                </div>
            );
        } else if (isAudio) {
             return (
                <div key={idx} className="p-3 rounded-xl border border-slate-600/50 shadow-lg bg-slate-900 flex items-center gap-3">
                    <div className="p-2 rounded-full bg-slate-800 text-yellow-400"><Music size={20} /></div>
                    <audio src={url} controls className="h-8 w-full max-w-[200px]" />
                </div>
            );
        } else {
            // PDF & Generic Files
            return (
                <a key={idx} href={url} download={att.name} className="flex items-center gap-3 p-4 rounded-xl border border-slate-600/50 bg-slate-900/80 hover:bg-slate-800 transition-all hover:border-slate-500 hover:shadow-lg group/file">
                    <div className={`p-3 rounded-lg bg-slate-800 group-hover/file:bg-slate-700 transition-colors ${isPdf ? 'text-red-400' : 'text-blue-400'}`}>
                        {isPdf ? <FileText size={24} /> : <File size={24} />}
                    </div>
                    <div className="min-w-0 flex-1">
                        <div className="text-sm font-bold text-slate-200 truncate">{att.name}</div>
                        <div className="text-xs text-slate-500 flex items-center gap-2">
                            <span className="uppercase">{att.mimeType.split('/')[1] || 'FILE'}</span>
                            <span>•</span>
                            <span>Document</span>
                        </div>
                    </div>
                    <div className="p-2 rounded-full hover:bg-slate-700 text-slate-500 group-hover/file:text-white transition-colors">
                        <Download size={18} />
                    </div>
                </a>
            );
        }
      })}
    </div>
  );
};
