
import React, { useMemo, useRef } from 'react';
import { Message, Role, AppMode } from '../../types/types';
import { Download, Maximize2, RefreshCw, ArrowRight, Image as ImageIcon, Video as VideoIcon, Layers, AlertCircle, Expand, Crop, Shirt } from 'lucide-react';

// 图片编辑模式列表（已拆分为独立模式）
const IMAGE_EDIT_MODES: AppMode[] = ['image-chat-edit', 'image-mask-edit', 'image-inpainting', 'image-background-edit', 'image-recontext'];

interface GenWorkspaceProps {
  messages: Message[];
  mode: AppMode;
  onImageClick: (url: string) => void;
  loadingState: string;
  onUploadReference?: (files: File[]) => void;
}

export const GenWorkspace: React.FC<GenWorkspaceProps> = ({
  messages,
  mode,
  onImageClick,
  loadingState,
  onUploadReference
}) => {
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Filter relevant results (Model messages with attachments or errors)
  const results = useMemo(() => {
    return messages
      .filter(m => m.role === Role.MODEL && ((m.attachments && m.attachments.length > 0) || m.isError))
      .flatMap(m => {
          if (m.isError) {
              return [{ id: m.id, isError: true, prompt: m.content, timestamp: m.timestamp, mimeType: 'error' } as any];
          }
          return m.attachments!.map(att => ({ ...att, timestamp: m.timestamp, prompt: m.content }));
      })
      .reverse();
  }, [messages]);

  const latestResult = results[0];
  
  // Find Reference Image (Crucial for Edit Mode)
  // We look for the latest user message with an image attachment
  const referenceImage = useMemo(() => {
      if (!IMAGE_EDIT_MODES.includes(mode) && mode !== 'image-outpainting' && mode !== 'virtual-try-on') return null;
      const lastUserMsg = [...messages].reverse().find(m => m.role === Role.USER && m.attachments && m.attachments.length > 0);
      return lastUserMsg?.attachments?.[0];
  }, [messages, mode]);

  const isVideo = mode === 'video-gen';
  const isEditMode = IMAGE_EDIT_MODES.includes(mode) || 
                     mode === 'image-outpainting' || mode === 'virtual-try-on';
  const isTryOnMode = mode === 'virtual-try-on';

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files && onUploadReference) {
          onUploadReference(Array.from(e.target.files));
      }
  };

  // --- Layout 1: Empty State for Edit/Outpaint/TryOn (Upload Zone) ---
  if (isEditMode && !referenceImage && loadingState === 'idle') {
      const getModeInfo = () => {
          if (isTryOnMode) return { title: 'Virtual Try-On', desc: 'Upload a person photo to try on clothes with AI.', icon: <Shirt size={36} /> };
          if (IMAGE_EDIT_MODES.includes(mode)) {
            return { title: 'Image Editing', desc: 'Upload an image to start transforming it with AI.', icon: <Crop size={36} /> };
          }
          return { title: 'Image Out-Painting', desc: 'Upload an image to start expanding it with AI.', icon: <Expand size={36} /> };
      };
      const modeInfo = getModeInfo();

      return (
          <div className="flex-1 flex flex-col items-center justify-center p-8 animate-[fadeIn_0.5s_ease-out]">
              <div className="max-w-xl w-full text-center mb-6">
                  <h2 className="text-3xl font-bold text-slate-100 mb-2">{modeInfo.title}</h2>
                  <p className="text-slate-400">{modeInfo.desc}</p>
              </div>
              
              <div 
                onClick={() => fileInputRef.current?.click()}
                className={`w-full max-w-lg aspect-video rounded-3xl border-2 border-dashed border-slate-700 ${isTryOnMode ? 'hover:border-rose-500' : 'hover:border-indigo-500'} bg-slate-900/50 hover:bg-slate-800/80 transition-all cursor-pointer flex flex-col items-center justify-center gap-4 group relative overflow-hidden`}
              >
                  <div className={`absolute inset-0 ${isTryOnMode ? 'bg-gradient-to-br from-rose-500/5 to-pink-500/5' : 'bg-gradient-to-br from-indigo-500/5 to-purple-500/5'} opacity-0 group-hover:opacity-100 transition-opacity`} />
                  <input type="file" ref={fileInputRef} onChange={handleFileChange} className="hidden" accept="image/*" />
                  <div className={`w-20 h-20 rounded-full bg-slate-800 ${isTryOnMode ? 'group-hover:bg-rose-600/20 group-hover:text-rose-400' : 'group-hover:bg-indigo-600/20 group-hover:text-indigo-400'} flex items-center justify-center text-slate-500 transition-colors z-10`}>
                      {modeInfo.icon}
                  </div>
                  <div className="text-center z-10">
                      <h3 className="text-xl font-semibold text-slate-200 group-hover:text-white">
                          {isTryOnMode ? 'Upload Person Photo' : 'Upload Reference Image'}
                      </h3>
                      <p className="text-sm text-slate-500 mt-2">Click to browse or drag & drop here</p>
                  </div>
              </div>
          </div>
      );
  }

  // --- Layout 2: Active Workspace (Gen or Edit Split View) ---
  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden">
      
      {/* Main Stage */}
      <div className="flex-1 p-4 flex gap-4 min-h-0 relative">
         
         {/* LEFT PANEL: Reference Image (Only visible in Edit/Outpaint modes when reference exists) */}
         {isEditMode && referenceImage && (
             <div className="flex-1 flex flex-col min-w-0 animate-[slideInLeft_0.3s_ease-out]">
                 <div className="flex items-center justify-between mb-2 px-1">
                     <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Source</span>
                     <button onClick={() => fileInputRef.current?.click()} className="text-xs text-indigo-400 hover:text-indigo-300 flex items-center gap-1 bg-slate-800/50 px-2 py-1 rounded hover:bg-slate-800">
                        <RefreshCw size={10} /> Replace
                     </button>
                     <input type="file" ref={fileInputRef} onChange={handleFileChange} className="hidden" accept="image/*" />
                 </div>
                 <div className="flex-1 bg-slate-900/50 rounded-2xl border border-slate-800 flex flex-col overflow-hidden relative group">
                     <img src={referenceImage.url} className="w-full h-full object-contain bg-[url('https://grainy-gradients.vercel.app/noise.svg')]" alt="Reference" />
                 </div>
             </div>
         )}

         {/* CENTER ARROW (Only if comparison) */}
         {isEditMode && referenceImage && (
             <div className="flex items-center justify-center text-slate-700">
                 <ArrowRight size={24} />
             </div>
         )}

         {/* RIGHT PANEL (or Full Center): Result */}
         <div className={`flex flex-col min-w-0 ${isEditMode && referenceImage ? 'flex-1' : 'w-full max-w-5xl mx-auto flex-[2]'}`}>
             {(isEditMode && referenceImage) && (
                 <div className="flex items-center justify-between mb-2 px-1">
                     <span className="text-xs font-bold text-slate-500 uppercase tracking-wider">Result</span>
                 </div>
             )}

             <div className="flex-1 bg-slate-900/50 rounded-2xl border border-slate-800 flex flex-col overflow-hidden relative group shadow-2xl transition-all">
                 
                 {loadingState !== 'idle' ? (
                     <div className="w-full h-full flex flex-col items-center justify-center gap-4 bg-slate-900/80">
                          <div className="relative">
                              <div className="w-16 h-16 border-4 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin"></div>
                              <div className="absolute inset-0 flex items-center justify-center text-xs font-mono text-indigo-400">
                                 {loadingState === 'uploading' ? 'UP' : 'AI'}
                              </div>
                          </div>
                          <div className="text-sm text-slate-400 animate-pulse font-mono">
                              {IMAGE_EDIT_MODES.includes(mode) ? 'EDITING...' : 
                               mode === 'image-outpainting' ? 'EXPANDING...' : 
                               mode === 'virtual-try-on' ? 'TRYING ON...' : 'GENERATING...'}
                          </div>
                     </div>
                 ) : latestResult ? (
                     latestResult.isError ? (
                        <div className="w-full h-full flex flex-col items-center justify-center text-red-400 gap-2 p-8 text-center">
                            <AlertCircle size={48} />
                            <h3 className="font-bold">Generation Failed</h3>
                            <p className="text-sm text-slate-400">{latestResult.prompt}</p>
                        </div>
                     ) : (
                        <>
                            {!isEditMode && (
                                <div className="absolute top-3 left-3 bg-indigo-600/80 backdrop-blur px-2 py-1 rounded text-xs text-white font-medium z-10 flex items-center gap-1.5 shadow-lg">
                                    {isVideo ? <VideoIcon size={12}/> : <Layers size={12}/>}
                                    Generated Result
                                </div>
                            )}
                            
                            <div className="w-full h-full flex items-center justify-center bg-[url('https://grainy-gradients.vercel.app/noise.svg')] bg-slate-950">
                                {isVideo ? (
                                    <video src={latestResult.url} controls autoPlay loop className="max-w-full max-h-full shadow-lg" />
                                ) : (
                                    <img 
                                        src={latestResult.url} 
                                        className="max-w-full max-h-full object-contain cursor-zoom-in" 
                                        onClick={() => onImageClick(latestResult.url!)}
                                        alt="Generated"
                                    />
                                )}
                            </div>

                            {/* Overlay Actions */}
                            <div className="absolute bottom-0 inset-x-0 p-4 bg-gradient-to-t from-black/80 to-transparent translate-y-full group-hover:translate-y-0 transition-transform">
                                <p className="text-sm text-white line-clamp-1 mb-2 font-medium">{latestResult.prompt}</p>
                                <div className="flex justify-end gap-2">
                                    <button onClick={() => onImageClick(latestResult.url!)} className="p-2 bg-white/10 hover:bg-white/20 rounded-lg text-white backdrop-blur"><Maximize2 size={18} /></button>
                                    <a href={latestResult.url} download className="p-2 bg-indigo-600 hover:bg-indigo-500 rounded-lg text-white shadow-lg"><Download size={18} /></a>
                                </div>
                            </div>
                        </>
                     )
                 ) : (
                     <div className="w-full h-full flex flex-col items-center justify-center text-slate-600 gap-3">
                         {isEditMode ? (
                             <>
                                <ArrowRight size={48} className="opacity-20" />
                                <p>Describe your edit and press Send.</p>
                             </>
                         ) : (
                             <>
                                <ImageIcon size={48} className="opacity-20" />
                                <p>Enter a prompt to start generating.</p>
                             </>
                         )}
                     </div>
                 )}
             </div>
         </div>
      </div>

      {/* History Gallery (Always Visible in Gen Mode) */}
      {results.length > 0 && (
          <div className="h-32 border-t border-slate-800 bg-slate-900/50 p-3 shrink-0 flex gap-3 overflow-x-auto custom-scrollbar">
              {results.map((att) => {
                  if (att.isError) return null;
                  return (
                    <div key={att.id} className="relative aspect-square rounded-lg overflow-hidden border border-slate-700 cursor-pointer hover:border-indigo-500 transition-all shrink-0 group">
                        {att.mimeType?.startsWith('video') ? (
                            <video src={att.url} className="w-full h-full object-cover opacity-60 group-hover:opacity-100" />
                        ) : (
                            <img src={att.url} className="w-full h-full object-cover opacity-60 group-hover:opacity-100" alt="History" />
                        )}
                        <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 flex items-center justify-center" onClick={() => onImageClick(att.url!)}>
                            <Maximize2 size={16} className="text-white drop-shadow-md" />
                        </div>
                    </div>
                  );
              })}
          </div>
      )}
    </div>
  );
};
