
import React from 'react';
import { X, FileText, Music, Video, File as FileIcon, Youtube } from 'lucide-react';
import { Attachment } from '../../../types/types';
import { CachedImage } from '../../common/CachedImage';
import { getPreferredImageAttachmentUrl } from '../../../utils/attachmentUrl';

export interface AttachmentPreviewRoleOption {
  value: string;
  label: string;
}

interface AttachmentPreviewProps {
  attachments: Attachment[];
  removeAttachment: (id: string) => void;
  getRoleOptions?: (attachment: Attachment) => AttachmentPreviewRoleOption[];
  onRoleChange?: (attachmentId: string, role: string) => void;
}

export const AttachmentPreview: React.FC<AttachmentPreviewProps> = ({
  attachments,
  removeAttachment,
  getRoleOptions,
  onRoleChange,
}) => {
  if (attachments.length === 0) return null;

  const getFileIcon = (att: Attachment) => {
      const mimeType = att.mimeType;
      if (att.name === 'YouTube Video' || (att.fileUri && att.fileUri.includes('youtube'))) return <Youtube size={24} className="text-red-500" />;
      if (mimeType.startsWith('image/')) return null; 
      if (mimeType.startsWith('video/')) return <Video size={20} className="text-pink-400" />;
      if (mimeType.startsWith('audio/')) return <Music size={20} className="text-yellow-400" />;
      if (mimeType.includes('pdf')) return <FileText size={20} className="text-red-400" />;
      return <FileIcon size={20} className="text-blue-400" />;
  };

  const getImageDisplayUrl = (attachment: Attachment): string | null =>
    getPreferredImageAttachmentUrl(attachment);

  return (
    <div className="flex gap-2 mb-2 overflow-x-auto p-1 custom-scrollbar justify-start">
      {attachments.map((att) => {
        const roleOptions = getRoleOptions?.(att) ?? [];
        const isImageAttachment = att.mimeType.startsWith('image/');
        const imageDisplayUrl = isImageAttachment ? getImageDisplayUrl(att) : null;
        const selectedRole =
          roleOptions.find((option) => option.value === att.role)?.value ??
          roleOptions[0]?.value ??
          '';

        return (
          <div key={att.id} className="relative group shrink-0 w-20">
              <div className="w-16 h-16 rounded-lg border border-slate-700 bg-slate-800 overflow-hidden flex flex-col items-center justify-center p-1 relative" title={att.name}>
                  {isImageAttachment && (imageDisplayUrl || att.file) ? (
                      <CachedImage
                        src={imageDisplayUrl}
                        source={{
                          ...att,
                          attachmentId: att.id,
                          url: imageDisplayUrl || undefined,
                          mimeType: att.mimeType,
                          name: att.name,
                        }}
                        alt={att.name}
                        className="w-full h-full object-cover"
                      />
                  ) : (
                      <div className="flex-1 flex items-center justify-center flex-col gap-1 text-center w-full px-1">
                        {getFileIcon(att)}
                        {att.name === 'YouTube Video' 
                            ? <span className="text-[8px] text-slate-400">YouTube</span>
                            : <span className="text-[8px] text-slate-400 truncate w-full px-1">{att.name}</span>
                        }
                      </div>
                  )}
              </div>
              <button 
                onClick={() => removeAttachment(att.id)} 
                className="absolute -top-1 -right-1 bg-slate-800 text-slate-400 rounded-full p-0.5 border border-slate-600 hover:text-white hover:bg-red-900/50 z-10"
              >
                <X size={10} />
              </button>
              {roleOptions.length > 0 && onRoleChange && (
                <label className="mt-1 block text-[10px] text-slate-500">
                  <span className="sr-only">素材角色 {att.name}</span>
                  <select
                    aria-label={`素材角色 ${att.name}`}
                    value={selectedRole}
                    onChange={(event) => onRoleChange(att.id, event.target.value)}
                    className="w-full rounded border border-slate-700 bg-slate-900 px-1 py-0.5 text-[10px] leading-4 text-slate-300 outline-none hover:border-slate-600 focus:border-indigo-500"
                  >
                    {roleOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </label>
              )}
          </div>
        );
      })}
    </div>
  );
};
