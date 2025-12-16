
import React, { useState, useRef, useEffect, useMemo } from 'react';
import { Message, Role, AppMode, Attachment, ChatOptions, ModelConfig } from '../../../types';
import { Crop, Wand2, UploadCloud, Download, AlertCircle, Layers, Image as ImageIcon, User, Bot, Trash2, Plus, Minus, RotateCcw, Move, Sparkles, Palette, PenTool, Expand, RefreshCw } from 'lucide-react';
import InputArea from '../chat/InputArea';

interface ImageEditViewProps {
  messages: Message[];
  setAppMode: (mode: AppMode) => void;
  onImageClick: (url: string) => void;
  loadingState: string;
  onSend: (text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => void;
  onStop: () => void;
  activeModelConfig?: ModelConfig;
  initialPrompt?: string;
  initialAttachments?: Attachment[];
  onExpandImage?: (url: string) => void; // Added prop
  providerId?: string;
}

export const ImageEditView: React.FC<ImageEditViewProps> = ({
  messages,
  setAppMode,
  onImageClick,
  loadingState,
  onSend,
  onStop,
  activeModelConfig,
  initialPrompt,
  initialAttachments,
  onExpandImage,
  providerId
}) => {
  const scrollRef = useRef<HTMLDivElement>(null);
  
  // State for reference image
  const [activeAttachments, setActiveAttachments] = useState<Attachment[]>([]);
  const [activeImageUrl, setActiveImageUrl] = useState<string | null>(null);
  
  // Track last processed message to auto-update view
  const [lastProcessedMsgId, setLastProcessedMsgId] = useState<string | null>(null);

  // --- Pan & Zoom State ---
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const dragStartRef = useRef({ x: 0, y: 0 });

  // Reset View when image changes
  useEffect(() => {
      setZoom(1);
      setPan({ x: 0, y: 0 });
  }, [activeImageUrl]);

  // Sync initial attachments
  useEffect(() => {
      if (initialAttachments && initialAttachments.length > 0) {
          setActiveAttachments(initialAttachments);
          setActiveImageUrl(initialAttachments[0].url || null);
      }
  }, [initialAttachments]);

  // Sync uploaded attachment to main view
  useEffect(() => {
      if (activeAttachments.length > 0 && activeAttachments[0].url) {
          setActiveImageUrl(activeAttachments[0].url);
      }
  }, [activeAttachments]);

  // Auto-scroll history
  useEffect(() => {
      if (scrollRef.current) {
          scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
      }
  }, [messages, activeAttachments]);

  // Auto-select latest result logic
  useEffect(() => {
      // 1. Initial Load: If no active image, pick latest from history
      if (activeAttachments.length === 0 && !activeImageUrl) {
          const lastModelMsg = [...messages].reverse().find(m => m.role === Role.MODEL && m.attachments?.length);
          if (lastModelMsg && lastModelMsg.attachments?.[0]?.url) {
              setActiveImageUrl(lastModelMsg.attachments[0].url);
          }
      }

      // 2. New Generation Complete: Auto-switch to result
      if (loadingState === 'idle' && messages.length > 0) {
          const lastMsg = messages[messages.length - 1];
          // Check if this is a new message we haven't handled yet
          if (lastMsg.id !== lastProcessedMsgId) {
              // If it's a model response with an image
              if (lastMsg.role === Role.MODEL && lastMsg.attachments && lastMsg.attachments.length > 0 && lastMsg.attachments[0].url) {
                  setActiveImageUrl(lastMsg.attachments[0].url);
                  setLastProcessedMsgId(lastMsg.id);
                  // Clear manual attachments to allow continuation from this result
                  setActiveAttachments([]);
              } else if (lastMsg.isError) {
                  setLastProcessedMsgId(lastMsg.id);
              }
          }
      }
  }, [messages, activeAttachments.length, loadingState, lastProcessedMsgId, activeImageUrl]);

  const handleSend = async (text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => {
      let finalAttachments = [...attachments];
      
      // CONTINUITY LOGIC (Multi-turn Edit)
      // If user didn't upload a NEW reference image, but we have an active image on canvas,
      // we reuse the canvas image as the input for the next edit.
      if (finalAttachments.length === 0 && activeImageUrl) {
          try {
              console.log("[ImageEdit] Reusing active image for continuity:", activeImageUrl.slice(0, 50) + "...");
              const response = await fetch(activeImageUrl);
              const blob = await response.blob();
              
              // Convert to Base64 to ensure provider compatibility
              const base64Url = await new Promise<string>((resolve) => {
                  const reader = new FileReader();
                  reader.onloadend = () => resolve(reader.result as string);
                  reader.readAsDataURL(blob);
              });

              const reusedAttachment: Attachment = {
                  id: crypto.randomUUID(),
                  mimeType: blob.type || 'image/png',
                  name: 'Previous Image Step',
                  url: base64Url
              };
              finalAttachments = [reusedAttachment];
          } catch (e) {
              console.error("Failed to reuse active image for continuity", e);
              // If fetch fails (e.g. strict CORS on remote URL), we might let it fail gracefully 
              // or alert user they need to re-upload.
          }
      }
      onSend(text, options, finalAttachments, mode);
  };

  // --- Canvas Event Handlers ---
  const handleWheel = (e: React.WheelEvent) => {
      if (!activeImageUrl) return;
      
      const scaleAmount = 0.1;
      const newZoom = e.deltaY > 0 ? zoom * (1 - scaleAmount) : zoom * (1 + scaleAmount);
      const clampedZoom = Math.min(Math.max(newZoom, 0.1), 5); // 0.1x to 5x
      setZoom(clampedZoom);
  };

  const handleMouseDown = (e: React.MouseEvent) => {
      if (!activeImageUrl) return;
      e.preventDefault();
      setIsDragging(true);
      dragStartRef.current = { 
          x: e.clientX - pan.x, 
          y: e.clientY - pan.y 
      };
  };

  const handleMouseMove = (e: React.MouseEvent) => {
      if (!isDragging) return;
      e.preventDefault();
      setPan({
          x: e.clientX - dragStartRef.current.x,
          y: e.clientY - dragStartRef.current.y
      });
  };

  const handleMouseUp = () => {
      setIsDragging(false);
  };

  const handleZoomIn = (e: React.MouseEvent) => { e.stopPropagation(); setZoom(z => Math.min(z + 0.2, 5)); };
  const handleZoomOut = (e: React.MouseEvent) => { e.stopPropagation(); setZoom(z => Math.max(z - 0.2, 0.1)); };
  const handleReset = (e: React.MouseEvent) => { e.stopPropagation(); setZoom(1); setPan({ x: 0, y: 0 }); };

  return (
      <div className="flex-1 flex flex-col h-full bg-slate-950 overflow-hidden">
          
          <div className="flex-1 flex overflow-hidden">
              
              {/* LEFT SIDEBAR: Source & History */}
              <div className="w-80 md:w-96 flex-shrink-0 border-r border-slate-800 bg-slate-900/30 flex flex-col z-20">
                  <div className="p-3 border-b border-slate-800 flex items-center justify-between bg-slate-900/50">
                      <span className="text-xs font-bold text-slate-400 uppercase tracking-wider flex items-center gap-2">
                          <Layers size={14} /> History
                      </span>
                  </div>
                  <div className="flex-1 overflow-y-auto p-4 space-y-6 custom-scrollbar" ref={scrollRef}>
                      {messages.map((msg) => {
                          const isPlaceholder = !msg.content && (!msg.attachments || msg.attachments.length === 0) && !msg.isError;
                          if (isPlaceholder) return null;

                          return (
                          <div key={msg.id} className={`flex flex-col gap-2 ${msg.role === Role.USER ? 'items-end' : 'items-start'}`}>
                              <div className="flex items-center gap-2 text-xs text-slate-500 px-1">
                                  {msg.role === Role.USER ? <User size={12} /> : <Bot size={12} />}
                                  <span>{msg.role === Role.USER ? 'You' : (activeModelConfig?.name || 'AI')}</span>
                              </div>
                              <div className={`p-3 rounded-2xl max-w-full text-sm shadow-sm ${
                                  msg.role === Role.USER 
                                  ? 'bg-slate-800 text-slate-200 rounded-tr-sm' 
                                  : 'bg-slate-800/50 text-slate-300 border border-slate-700/50 rounded-tl-sm'
                              }`}>
                                  {msg.content && <p className="mb-2">{msg.content}</p>}
                                  {msg.attachments?.map((att, idx) => (
                                      <div 
                                        key={idx} 
                                        onClick={() => setActiveImageUrl(att.url || null)}
                                        className={`relative group mt-1 rounded-lg overflow-hidden border cursor-pointer transition-all ${
                                            activeImageUrl === att.url ? 'ring-2 ring-pink-500 border-transparent' : 'border-slate-700 hover:border-slate-500'
                                        }`}
                                      >
                                          <img src={att.url} className="w-full h-32 object-cover bg-slate-900" alt="thumbnail" />
                                          <div className="absolute inset-0 bg-black/0 group-hover:bg-black/20 transition-colors flex items-center justify-center">
                                              {activeImageUrl === att.url && <div className="bg-pink-500 w-2 h-2 rounded-full absolute top-2 right-2 shadow-sm" />}
                                          </div>
                                      </div>
                                  ))}
                                  {msg.isError && (
                                      <div className="flex items-center gap-2 text-red-400 text-xs mt-1">
                                          <AlertCircle size={12} /> Error generating
                                      </div>
                                  )}
                              </div>
                          </div>
                          );
                      })}
                      {loadingState !== 'idle' && (
                          <div className="flex items-start gap-2 animate-pulse">
                              <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center"><Bot size={16} className="text-slate-500"/></div>
                              <div className="bg-slate-800/50 rounded-xl p-3 text-xs text-slate-400">Processing request...</div>
                          </div>
                      )}
                  </div>
              </div>

              {/* RIGHT MAIN: Result / Canvas */}
              <div 
                  className="flex-1 flex flex-col min-w-0 bg-slate-950 relative overflow-hidden select-none"
                  onWheel={handleWheel}
                  onMouseDown={handleMouseDown}
                  onMouseMove={handleMouseMove}
                  onMouseUp={handleMouseUp}
                  onMouseLeave={handleMouseUp}
                  style={{ cursor: isDragging ? 'grabbing' : activeImageUrl ? 'grab' : 'default' }}
              >
                  {/* Checkerboard Background */}
                  <div className="absolute inset-0 opacity-20 pointer-events-none" 
                       style={{ 
                           backgroundImage: `
                               linear-gradient(45deg, #334155 25%, transparent 25%), 
                               linear-gradient(-45deg, #334155 25%, transparent 25%), 
                               linear-gradient(45deg, transparent 75%, #334155 75%), 
                               linear-gradient(-45deg, transparent 75%, #334155 75%)
                           `,
                           backgroundSize: '20px 20px',
                           backgroundPosition: '0 0, 0 10px, 10px -10px, -10px 0px'
                       }} 
                  />

                  {/* Canvas Header */}
                  <div className="absolute top-4 left-4 z-10 pointer-events-none">
                      <div className="bg-black/60 backdrop-blur-md border border-white/10 rounded-full px-4 py-1.5 text-xs font-medium text-slate-300 flex items-center gap-2 shadow-lg">
                          <Wand2 size={12} className="text-pink-400" />
                          {activeAttachments.length > 0 && activeImageUrl === activeAttachments[0].url ? 'Source Image' : 'Workspace'}
                          <span className="opacity-50">|</span>
                          <span className="font-mono text-[10px] opacity-70">{Math.round(zoom * 100)}%</span>
                      </div>
                  </div>

                  {/* Main Image Display with Transformations */}
                  <div className="flex-1 flex items-center justify-center p-0 w-full h-full">
                      {loadingState !== 'idle' ? (
                         <div className="flex flex-col items-center gap-4 pointer-events-none">
                             <div className="relative">
                                  <div className="w-20 h-20 border-4 border-pink-500/30 border-t-pink-500 rounded-full animate-spin"></div>
                             </div>
                             <p className="text-slate-400 animate-pulse">Processing Image...</p>
                         </div>
                      ) : activeImageUrl ? (
                          <div 
                              className="relative shadow-2xl group transition-transform duration-75 ease-out"
                              style={{ 
                                  transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
                                  transformOrigin: 'center center'
                              }}
                          >
                               <img 
                                  src={activeImageUrl} 
                                  className="max-w-none rounded-lg border border-slate-800 pointer-events-none" 
                                  style={{ maxHeight: '80vh', maxWidth: '80vw' }} // Initial bounds
                                  alt="Main Canvas"
                               />
                          </div>
                      ) : (
                          <div className="text-center text-slate-600 pointer-events-none flex flex-col items-center gap-4 max-w-md">
                              <Crop size={48} className="opacity-20" />
                              <div>
                                  <h3 className="text-xl font-bold text-slate-500 mb-2">Editor Workspace</h3>
                                  <p className="text-sm opacity-60 mb-4">
                                      Attach an image below to start. Gemini allows advanced conversational editing:
                                  </p>
                                  <div className="grid grid-cols-2 gap-2 text-left text-xs opacity-50">
                                      <div className="flex items-center gap-2"><Palette size={12} /> Style Transfer</div>
                                      <div className="flex items-center gap-2"><Sparkles size={12} /> Inpainting/Replacing</div>
                                      <div className="flex items-center gap-2"><PenTool size={12} /> Sketch to Image</div>
                                      <div className="flex items-center gap-2"><Layers size={12} /> Composition</div>
                                  </div>
                              </div>
                          </div>
                      )}
                  </div>

                  {/* Floating Controls (Zoom/Reset) */}
                  {activeImageUrl && (
                      <div className="absolute bottom-6 right-6 z-20 flex flex-col gap-2">
                          <div className="bg-black/60 backdrop-blur-md border border-white/10 rounded-xl p-1.5 flex flex-col gap-1 shadow-xl">
                              <button onClick={handleZoomIn} className="p-2 hover:bg-white/10 rounded-lg text-slate-300 hover:text-white transition-colors" title="Zoom In">
                                  <Plus size={18} />
                              </button>
                              <button onClick={handleReset} className="p-2 hover:bg-white/10 rounded-lg text-slate-300 hover:text-white transition-colors" title="Reset View">
                                  <RotateCcw size={16} />
                              </button>
                              <button onClick={handleZoomOut} className="p-2 hover:bg-white/10 rounded-lg text-slate-300 hover:text-white transition-colors" title="Zoom Out">
                                  <Minus size={18} />
                              </button>
                          </div>
                          
                          {/* Actions Bar */}
                          <div className="bg-black/60 backdrop-blur-md border border-white/10 rounded-xl p-1.5 flex flex-col gap-1 shadow-xl">
                              {onExpandImage && (
                                  <button onClick={(e) => { e.stopPropagation(); onExpandImage(activeImageUrl!) }} className="p-2 hover:bg-orange-600/80 rounded-lg text-orange-400 hover:text-white transition-colors" title="Expand (Outpaint)">
                                      <Expand size={18} />
                                  </button>
                              )}
                              <button onClick={(e) => { e.stopPropagation(); onImageClick(activeImageUrl!) }} className="p-2 hover:bg-white/10 rounded-lg text-slate-300 hover:text-white transition-colors" title="Full Screen">
                                  <ImageIcon size={18} />
                              </button>
                              <a href={activeImageUrl} download onClick={(e) => e.stopPropagation()} className="p-2 hover:bg-pink-600/80 rounded-lg text-pink-400 hover:text-white transition-colors" title="Download">
                                  <Download size={18} />
                              </a>
                          </div>
                      </div>
                  )}
              </div>

          </div>

          {/* Bottom Input Area */}
          <div className="p-4 border-t border-slate-800 bg-slate-900 z-30">
              <div className="max-w-4xl mx-auto">
                  
                  {/* Visual Context Indicator */}
                  {activeImageUrl && activeAttachments.length === 0 && (
                      <div className="flex items-center gap-2 mb-2 ml-1 animate-[fadeIn_0.3s_ease-out]">
                          <div className="w-1 h-4 bg-pink-500 rounded-full"></div>
                          <span className="text-xs text-pink-300 font-medium flex items-center gap-1">
                              <RefreshCw size={10} className="animate-[spin_4s_linear_infinite]" />
                              Editing active image context
                          </span>
                      </div>
                  )}

                  <InputArea 
                      onSend={handleSend}
                      isLoading={loadingState !== 'idle'}
                      onStop={onStop}
                      currentModel={activeModelConfig}
                      mode="image-edit"
                      setMode={setAppMode}
                      initialPrompt={initialPrompt}
                      // Sync State
                      activeAttachments={activeAttachments}
                      onAttachmentsChange={setActiveAttachments}
                      hasActiveContext={!!activeImageUrl}
                      providerId={providerId}
                  />
              </div>
          </div>
      </div>
  );
};
