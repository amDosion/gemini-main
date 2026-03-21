
import React, { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { Message, Role, AppMode, Attachment, ChatOptions, ModelConfig } from '../../types/types';
import { Mic, Clock, AlertCircle, User, Bot, Download, Maximize2, Volume2, SlidersHorizontal, RotateCcw } from 'lucide-react';
import { GenViewLayout } from '../common/GenViewLayout';
import { useControlsState } from '../../hooks/useControlsState';
import { ModeControlsCoordinator } from '../../coordinators/ModeControlsCoordinator';
import ChatEditInputArea from '../chat/ChatEditInputArea';

interface AudioGenViewProps {
  messages: Message[];
  setAppMode: (mode: AppMode) => void;
  loadingState: string;
  onSend: (text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => void;
  onStop: () => void;
  activeModelConfig?: ModelConfig;
  visibleModels?: ModelConfig[];
  allVisibleModels?: ModelConfig[];
  initialPrompt?: string;
  providerId?: string;
}

interface Word {
  text: string;
  time: number; // Time allocated for this word
  startTime: number; // Cumulative start time
  endTime: number; // Cumulative end time
}

interface Line {
  words: Word[];
  totalTime: number;
  startTime: number;
  endTime: number;
}

const getAttachmentStableKey = (attachment: Attachment): string => {
  const parts = [
    attachment.id,
    attachment.url,
    attachment.fileUri,
    attachment.name,
    attachment.mimeType,
  ].filter((part): part is string => Boolean(part && part.length > 0));

  return parts.join('|');
};

const getLineStableKey = (line: Line, isCurrent: boolean): string => {
  return `${isCurrent ? 'current' : 'next'}:${line.startTime}:${line.endTime}`;
};

const getWordStableKey = (word: Word): string => {
  return `${word.startTime}:${word.endTime}:${word.text}`;
};

// Component for true Karaoke-style lyrics display
const KaraokeLyrics: React.FC<{ text: string; currentTime: number; duration: number }> = ({
  text,
  currentTime,
  duration
}) => {
  // Parse text into lines and words with time allocation
  const lines = useMemo(() => {
    if (!text || duration === 0) return [];

    // Split text into lines (preserve line breaks)
    const textLines = text.split('\n').filter(line => line.trim().length > 0);
    if (textLines.length === 0) return [];

    // Calculate total characters and words for time distribution
    const totalChars = text.replace(/\s+/g, '').length; // Total non-whitespace characters
    const charsPerSecond = totalChars / duration;

    // Process each line
    const processedLines: Line[] = [];
    let cumulativeTime = 0;

    textLines.forEach((lineText) => {
      // Split line into words (preserving spaces)
      const words: Word[] = [];
      const wordMatches = lineText.matchAll(/(\S+)|(\s+)/g);
      let wordStartTime = cumulativeTime;

      for (const match of wordMatches) {
        const wordText = match[0];
        const isWord = match[1] !== undefined; // Not whitespace

        if (isWord) {
          // Calculate time based on character count (longer words take more time)
          // Add base time for word boundary and pronunciation overhead
          const charCount = wordText.length;
          const wordTime = (charCount / charsPerSecond) + (0.1 * charCount); // Base time + per char overhead

          words.push({
            text: wordText,
            time: wordTime,
            startTime: wordStartTime,
            endTime: wordStartTime + wordTime
          });

          wordStartTime += wordTime;
        } else {
          // Whitespace - minimal time, but still some for natural pause
          const spaceTime = 0.05;
          wordStartTime += spaceTime;
        }
      }

      const lineTotalTime = wordStartTime - cumulativeTime;
      processedLines.push({
        words,
        totalTime: lineTotalTime,
        startTime: cumulativeTime,
        endTime: cumulativeTime + lineTotalTime
      });

      cumulativeTime += lineTotalTime;
    });

    // Scale to fit actual duration
    const calculatedDuration = cumulativeTime;
    if (calculatedDuration > 0) {
      const scaleFactor = duration / calculatedDuration;
      processedLines.forEach(line => {
        line.startTime *= scaleFactor;
        line.endTime *= scaleFactor;
        line.totalTime *= scaleFactor;
        line.words.forEach(word => {
          word.time *= scaleFactor;
          word.startTime *= scaleFactor;
          word.endTime *= scaleFactor;
        });
      });
    }

    return processedLines;
  }, [text, duration]);

  // Find current line and word
  const { currentLineIndex, currentWordIndex, lineProgress } = useMemo(() => {
    if (lines.length === 0) return { currentLineIndex: -1, currentWordIndex: -1, lineProgress: 0 };

    // Find which line we're in
    let lineIdx = -1;
    for (let i = 0; i < lines.length; i++) {
      if (currentTime >= lines[i].startTime && currentTime <= lines[i].endTime) {
        lineIdx = i;
        break;
      } else if (currentTime > lines[i].endTime && i === lines.length - 1) {
        // Past last line
        lineIdx = i;
        break;
      }
    }

    if (lineIdx === -1) {
      // Before first line
      return { currentLineIndex: 0, currentWordIndex: -1, lineProgress: 0 };
    }

    const currentLine = lines[lineIdx];

    // Find which word we're in within the current line
    let wordIdx = -1;
    for (let i = 0; i < currentLine.words.length; i++) {
      if (currentTime >= currentLine.words[i].startTime && currentTime <= currentLine.words[i].endTime) {
        wordIdx = i;
        break;
      } else if (currentTime > currentLine.words[i].endTime && i === currentLine.words.length - 1) {
        wordIdx = i;
        break;
      }
    }

    // Calculate progress within current word (for smooth highlighting)
    let wordProgress = 0;
    if (wordIdx >= 0 && wordIdx < currentLine.words.length) {
      const word = currentLine.words[wordIdx];
      if (word.time > 0) {
        wordProgress = Math.min(1, Math.max(0, (currentTime - word.startTime) / word.time));
      }
    }

    return {
      currentLineIndex: lineIdx,
      currentWordIndex: wordIdx,
      lineProgress: wordProgress
    };
  }, [currentTime, lines]);

  // Display strategy: show current line and next line (if available)
  const displayLines = useMemo(() => {
    if (lines.length === 0) return [];

    const display: Array<{ line: Line; isCurrent: boolean; wordIndex: number; wordProgress: number }> = [];

    // Always show current line
    if (currentLineIndex >= 0 && currentLineIndex < lines.length) {
      display.push({
        line: lines[currentLineIndex],
        isCurrent: true,
        wordIndex: currentWordIndex,
        wordProgress: lineProgress
      });
    }

    // Show next line if available
    if (currentLineIndex >= 0 && currentLineIndex < lines.length - 1) {
      display.push({
        line: lines[currentLineIndex + 1],
        isCurrent: false,
        wordIndex: -1,
        wordProgress: 0
      });
    }

    return display;
  }, [lines, currentLineIndex, currentWordIndex, lineProgress]);

  if (!text || lines.length === 0) return null;

  return (
    <div className="flex flex-col gap-4 items-center">
      {displayLines.map((displayLine) => {
        const { line, isCurrent, wordIndex, wordProgress } = displayLine;

        return (
          <div
            key={getLineStableKey(line, isCurrent)}
            className={`text-xl leading-relaxed transition-all duration-300 ${isCurrent
              ? 'text-slate-100 font-medium'
              : 'text-slate-500 font-normal opacity-60'
              }`}
            style={{
              transform: isCurrent ? 'translateY(0)' : 'translateY(10px)',
            }}
          >
            {line.words.map((word, wordIdx) => {
              const isPlayed = wordIdx < wordIndex;
              const isCurrentWord = wordIdx === wordIndex;

              return (
                <span
                  key={getWordStableKey(word)}
                  className={`inline-block transition-colors duration-100 ${isPlayed
                    ? 'text-cyan-400 font-semibold' // Already played words
                    : isCurrentWord
                      ? 'text-cyan-300 font-bold' // Current word being highlighted
                      : 'text-slate-400' // Upcoming words
                    }`}
                  style={{
                    // Smooth transition for current word
                    ...(isCurrentWord && {
                      background: `linear-gradient(to right, 
                        #22d3ee 0%, 
                        #22d3ee ${wordProgress * 100}%, 
                        #94a3b8 ${wordProgress * 100}%, 
                        #94a3b8 100%
                      )`,
                      WebkitBackgroundClip: 'text',
                      backgroundClip: 'text',
                      WebkitTextFillColor: 'transparent',
                    })
                  }}
                >
                  {word.text}
                  {wordIdx < line.words.length - 1 && ' '}
                </span>
              );
            })}
          </div>
        );
      })}
    </div>
  );
};

export const AudioGenView: React.FC<AudioGenViewProps> = ({
  messages,
  setAppMode,
  loadingState,
  onSend,
  onStop,
  activeModelConfig,
  visibleModels = [],
  allVisibleModels = [],
  initialPrompt,
  providerId
}) => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const audioRef = useRef<HTMLAudioElement>(null);

  // State for the currently displayed audio in the main stage
  const [activeAudioUrl, setActiveAudioUrl] = useState<string | null>(null);
  // State for the text content corresponding to the active audio (for lyrics display)
  const [activeAudioText, setActiveAudioText] = useState<string>('');
  // State for audio playback status
  const [isPlaying, setIsPlaying] = useState(false);
  // State for audio playback progress (for karaoke effect)
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);

  // ✅ 参数面板状态
  const audioMode: AppMode = 'audio-gen';
  const controls = useControlsState(audioMode, activeModelConfig);

  // 重置参数
  const resetParams = useCallback(() => {
    controls.setVoice('Puck');
  }, [controls]);

  // Auto-scroll history to bottom when messages change
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  // Auto-select the latest generated audio when loading finishes
  useEffect(() => {
    if (loadingState === 'idle') {
      // Find the latest successful model message with an audio attachment
      const lastModelMsg = [...messages].reverse().find(m =>
        m.role === Role.MODEL &&
        m.attachments?.some(a => a.mimeType.startsWith('audio/')) &&
        !m.isError
      );

      if (lastModelMsg) {
        const audioAtt = lastModelMsg.attachments?.find(a => a.mimeType.startsWith('audio/'));
        if (audioAtt?.url) {
          setActiveAudioUrl(audioAtt.url);
          // Find the corresponding user message to get the text content
          const modelMsgIndex = messages.findIndex(m => m.id === lastModelMsg.id);
          if (modelMsgIndex > 0) {
            const userMsg = messages[modelMsgIndex - 1];
            if (userMsg && userMsg.role === Role.USER && userMsg.content) {
              setActiveAudioText(userMsg.content);
            }
          }
        }
      }
    }
  }, [loadingState, messages]);

  // Handle audio playback events and progress tracking
  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return;

    const handlePlay = () => setIsPlaying(true);
    const handlePause = () => setIsPlaying(false);
    const handleEnded = () => {
      setIsPlaying(false);
      setCurrentTime(0);
    };
    const handleTimeUpdate = () => {
      setCurrentTime(audio.currentTime);
    };
    const handleLoadedMetadata = () => {
      setDuration(audio.duration);
    };
    const handleLoadedData = () => {
      setDuration(audio.duration);
    };

    audio.addEventListener('play', handlePlay);
    audio.addEventListener('pause', handlePause);
    audio.addEventListener('ended', handleEnded);
    audio.addEventListener('timeupdate', handleTimeUpdate);
    audio.addEventListener('loadedmetadata', handleLoadedMetadata);
    audio.addEventListener('loadeddata', handleLoadedData);

    // Initialize duration if already loaded
    if (audio.duration) {
      setDuration(audio.duration);
    }

    return () => {
      audio.removeEventListener('play', handlePlay);
      audio.removeEventListener('pause', handlePause);
      audio.removeEventListener('ended', handleEnded);
      audio.removeEventListener('timeupdate', handleTimeUpdate);
      audio.removeEventListener('loadedmetadata', handleLoadedMetadata);
      audio.removeEventListener('loadeddata', handleLoadedData);
    };
  }, [activeAudioUrl]);

  // Reset progress when audio URL changes
  useEffect(() => {
    setCurrentTime(0);
    setIsPlaying(false);
  }, [activeAudioUrl]);

  // Update active audio and text when clicking on audio in history
  const handleAudioClick = useCallback((url: string) => {
    setActiveAudioUrl(url);
    // Find the message containing this audio
    const modelMsg = messages.find(m =>
      m.attachments?.some(a => a.url === url)
    );
    if (modelMsg) {
      const modelMsgIndex = messages.findIndex(m => m.id === modelMsg.id);
      if (modelMsgIndex > 0) {
        const userMsg = messages[modelMsgIndex - 1];
        if (userMsg && userMsg.role === Role.USER && userMsg.content) {
          setActiveAudioText(userMsg.content);
        }
      }
    }
  }, [messages]);

  const handleDownload = useCallback((url: string) => {
    const link = document.createElement('a');
    link.href = url;
    link.download = `gemini-audio-${Date.now()}.wav`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }, []);

  // ✅ ChatEditInputArea 已经处理了附件和参数，这里只需要直接转发
  // 注意：需要保留 prompt 用于 Karaoke 显示
  const handleSend = useCallback((text: string, options: ChatOptions, attachments: Attachment[], mode: AppMode) => {
    setActiveAudioText(text); // 保留用于 Karaoke 显示
    onSend(text, options, attachments, audioMode);
  }, [onSend, audioMode]);

  // Get current audio text for lyrics display
  const getActiveAudioText = useCallback((): string => {
    if (activeAudioText) return activeAudioText;
    // Fallback: try to find from current active audio URL
    const modelMsg = messages.find(m =>
      m.attachments?.some(a => a.url === activeAudioUrl)
    );
    if (modelMsg) {
      const modelMsgIndex = messages.findIndex(m => m.id === modelMsg.id);
      if (modelMsgIndex > 0) {
        const userMsg = messages[modelMsgIndex - 1];
        if (userMsg && userMsg.role === Role.USER && userMsg.content) {
          return userMsg.content;
        }
      }
    }
    return '';
  }, [messages, activeAudioUrl, activeAudioText]);

  // Mobile History Toggle
  const [isMobileHistoryOpen, setIsMobileHistoryOpen] = useState(false);

  // 缓存 sidebarContent
  const sidebarContent = useMemo(() => (
        <div className="flex-1 overflow-y-auto p-4 space-y-6 custom-scrollbar" ref={scrollRef}>
          {messages.map((msg) => {
            // Filter out empty placeholders to prevent "Double Bubble" issue
            const isPlaceholder = !msg.content && (!msg.attachments || msg.attachments.length === 0) && !msg.isError;
            if (isPlaceholder) return null;

            return (
              <div key={msg.id} className={`flex flex-col gap-2 ${msg.role === Role.USER ? 'items-end' : 'items-start'}`}>

                {/* Role Label */}
                <div className="flex items-center gap-2 text-xs text-slate-500 px-1">
                  {msg.role === Role.USER ? <User size={12} /> : <Bot size={12} />}
                  <span>{msg.role === Role.USER ? 'You' : (activeModelConfig?.name || 'AI')}</span>
                </div>

                {/* Message Bubble */}
                <div className={`p-3 rounded-2xl max-w-full text-sm shadow-sm border ${msg.role === Role.USER
                  ? 'bg-slate-800 text-slate-200 border-slate-700/50 rounded-tr-sm'
                  : 'bg-slate-800/50 text-slate-300 border-slate-700/50 rounded-tl-sm'
                  }`}>
                  {msg.content && <p className="mb-2 whitespace-pre-wrap">{msg.content}</p>}

                  {/* Attachments (Audio) */}
                  {msg.attachments?.map((att) => {
                    const isAudio = att.mimeType.startsWith('audio/');
                    const isActive = activeAudioUrl === att.url;

                    return (
                      <div
                        key={`${msg.id}:${getAttachmentStableKey(att)}`}
                        onClick={() => att.url && isAudio && handleAudioClick(att.url)}
                        className={`relative group mt-2 rounded-lg overflow-hidden border transition-all ${isAudio ? 'cursor-pointer' : ''
                          } ${isActive ? 'ring-2 ring-cyan-500 border-transparent' : 'border-slate-700 hover:border-slate-500'
                          }`}
                      >
                        {isAudio ? (
                          <div className="p-4 bg-slate-900/50 flex items-center gap-3">
                            <div className={`p-2 rounded-lg ${isActive ? 'bg-cyan-500/20 text-cyan-400' : 'bg-slate-800 text-slate-400'
                              }`}>
                              <Mic size={20} />
                            </div>
                            <div className="flex-1 min-w-0">
                              <p className="text-xs font-medium text-slate-300 truncate">
                                {att.name || 'Generated Audio'}
                              </p>
                              <p className="text-[10px] text-slate-500 mt-0.5">
                                {att.mimeType.replace('audio/', '').toUpperCase()}
                              </p>
                            </div>
                            {isActive && (
                              <div className="w-2 h-2 rounded-full bg-cyan-500 animate-pulse" />
                            )}
                          </div>
                        ) : (
                          <div className="p-2 bg-slate-900 flex items-center gap-2 text-xs">
                            <Volume2 size={14} /> {att.name}
                          </div>
                        )}
                      </div>
                    );
                  })}

                  {/* Error State */}
                  {msg.isError && (
                    <div className="flex items-center gap-2 text-red-400 text-xs mt-2 p-2 bg-red-900/10 rounded">
                      <AlertCircle size={12} />
                      <span>Generation failed</span>
                    </div>
                  )}
                </div>
              </div>
            );
          })}

          {/* Loading Indicator */}
          {loadingState !== 'idle' && (
            <div className="flex items-start gap-2 animate-pulse">
              <div className="w-8 h-8 rounded-full bg-slate-800 flex items-center justify-center">
                <Bot size={16} className="text-slate-500" />
              </div>
              <div className="bg-slate-800/50 rounded-xl p-3 text-xs text-slate-400 border border-slate-700/50">
                Generating speech... This may take a moment.
              </div>
            </div>
          )}

          {messages.length === 0 && (
            <div className="text-center py-10 text-slate-600 text-xs italic">
              No history yet. Start by entering text to convert to speech!
            </div>
          )}
        </div>
  ), [messages, loadingState, activeModelConfig?.name, activeAudioUrl, handleAudioClick]);

  // ✅ 主区域：两栏布局（画布 + 参数面板）
  const mainContent = useMemo(() => (
    <div className="flex-1 flex flex-row h-full">
      {/* ========== 左侧：画布区域 ========== */}
      <div className="flex-1 flex flex-col items-center justify-center p-8 overflow-hidden bg-slate-950 relative">
        {/* 棋盘格背景 */}
        <div
          className="absolute inset-0 opacity-20 pointer-events-none"
          style={{
            backgroundImage: `
              linear-gradient(45deg, #334155 25%, transparent 25%), 
              linear-gradient(-45deg, #334155 25%, transparent 25%), 
              linear-gradient(45deg, transparent 75%, #334155 75%), 
              linear-gradient(-45deg, transparent 75%, #334155 75%)
            `,
            backgroundSize: '20px 20px',
            backgroundPosition: '0 0, 0 10px, 10px -10px, -10px 0px',
          }}
        />
        {/* Canvas Header */}
        <div className="absolute top-4 left-4 z-10 pointer-events-none">
          <div className="bg-black/60 backdrop-blur-md border border-white/10 rounded-full px-4 py-1.5 text-xs font-medium text-slate-300 flex items-center gap-2 shadow-lg">
            <Mic size={12} className="text-cyan-400" />
            Audio Workspace
          </div>
        </div>

        {/* Main Content */}
        <div className="flex-1 flex items-center justify-center p-8 overflow-hidden w-full relative z-10">
          {loadingState !== 'idle' ? (
            <div className="flex flex-col items-center gap-6 p-8 rounded-3xl bg-slate-900/50 backdrop-blur-sm border border-slate-800/50 shadow-2xl relative z-10">
              <div className="relative">
                <div className="w-24 h-24 border-4 border-cyan-500/30 border-t-cyan-500 rounded-full animate-spin"></div>
                <div className="absolute inset-0 flex items-center justify-center text-sm font-mono text-cyan-400 font-bold tracking-widest">TTS</div>
              </div>
              <div className="text-center">
                <p className="text-slate-200 font-medium text-lg">Generating Speech...</p>
                <p className="text-slate-500 text-xs mt-1">Converting text to audio.</p>
              </div>
            </div>
          ) : activeAudioUrl ? (
            <div className="relative max-w-2xl w-full shadow-2xl rounded-xl overflow-hidden bg-slate-900/80 backdrop-blur-sm ring-1 ring-white/10 flex flex-col items-center justify-center p-8 gap-6 z-10">
              <div className="p-6 bg-cyan-500/10 rounded-full text-cyan-400">
                <Mic size={64} />
              </div>
              <audio
                ref={audioRef}
                src={activeAudioUrl}
                controls
                autoPlay
                className="w-full max-w-md"
              />

              {/* Karaoke Lyrics Display */}
              {getActiveAudioText() && (
                <div className="mt-4 w-full max-w-2xl">
                  <div className="bg-slate-800/60 backdrop-blur-sm rounded-xl p-8 border border-slate-700/50 min-h-[200px] flex items-center justify-center">
                    <div className="w-full">
                      <div className="text-xs text-slate-400 uppercase tracking-wider mb-6 flex items-center gap-2 justify-center">
                        <Volume2 size={14} />
                        <span>Karaoke Mode</span>
                        {isPlaying && (
                          <div className="ml-4 flex items-center gap-2 text-cyan-400">
                            <div className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse"></div>
                            <span className="text-xs">Playing</span>
                          </div>
                        )}
                      </div>
                      <KaraokeLyrics
                        text={getActiveAudioText()}
                        currentTime={currentTime}
                        duration={duration}
                      />
                    </div>
                  </div>
                  {duration > 0 && (
                    <div className="mt-4 text-xs text-slate-500 flex items-center justify-between px-2">
                      <span>{Math.floor(currentTime)}s / {Math.floor(duration)}s</span>
                      <span>{duration > 0 ? Math.round((currentTime / duration) * 100) : 0}%</span>
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : (
            <div className="text-center text-slate-600 flex flex-col items-center gap-6 relative z-10">
              <div className="w-32 h-32 rounded-3xl bg-slate-900 border border-slate-800 flex items-center justify-center shadow-inner relative overflow-hidden group">
                <div className="absolute inset-0 bg-gradient-to-tr from-cyan-500/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
                <Mic size={64} className="opacity-20 group-hover:scale-110 transition-transform duration-500" />
              </div>
              <div>
                <h3 className="text-2xl font-bold text-slate-500 mb-2">Text to Speech</h3>
                <p className="max-w-xs mx-auto text-sm opacity-60">
                  Enter text below to convert it into natural-sounding speech.
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Action Buttons - Fixed in bottom right of main stage */}
        {activeAudioUrl && (
          <div className="absolute bottom-4 right-4 z-20 flex gap-2 relative">
            <button
              onClick={() => window.open(activeAudioUrl, '_blank')}
              className="p-2.5 bg-black/60 backdrop-blur-md hover:bg-black/80 text-white rounded-xl border border-white/10 transition-colors shadow-lg"
              title="Open in new tab"
            >
              <Maximize2 size={20} />
            </button>
            <button
              onClick={() => handleDownload(activeAudioUrl)}
              className="p-2.5 bg-cyan-600 hover:bg-cyan-500 text-white rounded-xl shadow-lg transition-colors flex items-center gap-2 border border-cyan-500/30"
              title="Download"
            >
              <Download size={20} />
              <span className="text-xs font-bold pr-1">Download</span>
            </button>
          </div>
        )}
      </div>

      {/* ========== 右侧：参数面板 ========== */}
      <div className="w-72 flex-shrink-0 border-l border-slate-800 bg-slate-900/50 flex flex-col h-full overflow-hidden">
        {/* 头部 */}
        <div className="px-4 py-3 border-b border-slate-800/50 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <SlidersHorizontal size={14} className="text-cyan-400" />
            <span className="text-xs font-bold text-white">音频参数</span>
          </div>
          <button
            onClick={resetParams}
            className="p-1.5 rounded-lg hover:bg-slate-800 text-slate-400 hover:text-white transition-colors"
            title="重置为默认值"
          >
            <RotateCcw size={12} />
          </button>
        </div>

        {/* 参数滚动区 */}
        <div className="flex-1 overflow-y-auto custom-scrollbar p-4">
          <ModeControlsCoordinator
            mode={audioMode}
            providerId={providerId || 'google'}
            controls={controls}
          />
        </div>

        {/* 底部固定区：使用 ChatEditInputArea 组件 */}
        <ChatEditInputArea
          onSend={handleSend}
          isLoading={loadingState !== 'idle'}
          onStop={onStop}
          mode={audioMode}
          activeAttachments={[]}
          onAttachmentsChange={() => {}}
          activeImageUrl={null}
          onActiveImageUrlChange={() => {}}
          messages={messages}
          sessionId={null}
          initialPrompt={initialPrompt}
          providerId={providerId}
          controls={controls}
        />
      </div>
    </div>
  ), [loadingState, activeAudioUrl, audioRef, isPlaying, currentTime, duration, getActiveAudioText, handleDownload, controls, providerId, resetParams, audioMode, activeModelConfig, onStop, messages, initialPrompt, handleSend]);

  return (
    <GenViewLayout
      isMobileHistoryOpen={isMobileHistoryOpen}
      setIsMobileHistoryOpen={setIsMobileHistoryOpen}
      sidebarTitle="History"
      sidebarHeaderIcon={<Clock size={14} />}
      sidebar={sidebarContent}
      main={mainContent}
    />
  );
};
