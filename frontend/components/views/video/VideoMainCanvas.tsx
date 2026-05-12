/**
 * VideoGenView 主区（视频画布 + 自定义播放控件条 + 右侧参数面板 + 输入区）。
 *
 * 1:1 抽离自 `VideoGenView.tsx` L1108-1463 mainContent useMemo body。
 */

import React from 'react';
import {
  AlertCircle,
  Download,
  Film,
  Maximize2,
  Pause,
  Play,
  Video as VideoIcon,
  Volume2,
  VolumeX,
} from 'lucide-react';
import type { AppMode, Attachment, ChatOptions, Message, ModelConfig } from '../../../types/types';
import type { ControlsState } from '../../../controls/types';
import { ModeControlsCoordinator } from '../../../coordinators/ModeControlsCoordinator';
import ChatEditInputArea from '../../chat/ChatEditInputArea';
import { ViewSideParamsPanel } from '../../common/ViewSideParamsPanel';

export interface VideoMainCanvasProps {
  // workspace state
  loadingState: string;
  isBatchError: boolean;
  activeBatchMessage: Message | undefined;
  activeVideoUrl: string | null;
  activeSubtitleTrack: Attachment | null;
  downloadableSubtitleAttachment: Attachment | null;
  // player state/refs/handlers (from useVideoPlayerControls)
  activeVideoRef: React.MutableRefObject<HTMLVideoElement | null>;
  activeVideoStageRef: React.MutableRefObject<HTMLDivElement | null>;
  videoSeekInputRef: React.MutableRefObject<HTMLInputElement | null>;
  videoProgressFillRef: React.MutableRefObject<HTMLDivElement | null>;
  videoProgressThumbRef: React.MutableRefObject<HTMLDivElement | null>;
  videoCurrentTimeLabelRef: React.MutableRefObject<HTMLSpanElement | null>;
  isVideoPlaying: boolean;
  setIsVideoPlaying: React.Dispatch<React.SetStateAction<boolean>>;
  videoDuration: number;
  setVideoDuration: React.Dispatch<React.SetStateAction<number>>;
  isVideoFullscreen: boolean;
  isVideoMuted: boolean;
  videoVolume: number;
  toggleActiveVideoPlayback: () => Promise<void> | void;
  handleToggleFullscreen: () => Promise<void> | void;
  handleToggleMute: () => void;
  handleActiveVideoSeek: (event: React.ChangeEvent<HTMLInputElement>) => void;
  handleActiveVideoVolumeChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
  syncVideoProgressUi: (currentTime: number, duration: number) => void;
  formatVideoTime: (timeInSeconds: number) => string;
  handleDownload: (url: string) => void;
  // params panel
  videoMode: AppMode;
  resolvedProviderId: string;
  activeModelConfig?: ModelConfig;
  controls: ControlsState;
  resetParams: () => void;
  // input area
  handleSend: (
    text: string,
    options: ChatOptions,
    attachments: Attachment[],
    mode: AppMode
  ) => void;
  onStop: () => void;
  activeAttachments: Attachment[];
  setActiveAttachments: React.Dispatch<React.SetStateAction<Attachment[]>>;
  activeImageUrl: string | null;
  setActiveImageUrl: React.Dispatch<React.SetStateAction<string | null>>;
  messages: Message[];
  sessionId?: string | null;
  initialPrompt?: string;
  videoControlsStatusMessage: string | null;
}

export const VideoMainCanvas: React.FC<VideoMainCanvasProps> = ({
  loadingState,
  isBatchError,
  activeBatchMessage,
  activeVideoUrl,
  activeSubtitleTrack,
  downloadableSubtitleAttachment,
  activeVideoRef,
  activeVideoStageRef,
  videoSeekInputRef,
  videoProgressFillRef,
  videoProgressThumbRef,
  videoCurrentTimeLabelRef,
  isVideoPlaying,
  setIsVideoPlaying,
  videoDuration,
  setVideoDuration,
  isVideoFullscreen,
  isVideoMuted,
  videoVolume,
  toggleActiveVideoPlayback,
  handleToggleFullscreen,
  handleToggleMute,
  handleActiveVideoSeek,
  handleActiveVideoVolumeChange,
  syncVideoProgressUi,
  formatVideoTime,
  handleDownload,
  videoMode,
  resolvedProviderId,
  activeModelConfig,
  controls,
  resetParams,
  handleSend,
  onStop,
  activeAttachments,
  setActiveAttachments,
  activeImageUrl,
  setActiveImageUrl,
  messages,
  sessionId,
  initialPrompt,
  videoControlsStatusMessage,
}) => {
  return (
    <div className="flex-1 flex flex-row h-full">
      <div className="flex-1 flex flex-col items-center justify-center p-8 overflow-hidden bg-slate-950 relative">
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

        <div className="absolute top-4 left-4 z-10 pointer-events-none">
          <div className="bg-black/60 backdrop-blur-md border border-white/10 rounded-full px-4 py-1.5 text-xs font-medium text-slate-300 flex items-center gap-2 shadow-lg">
            <Film size={12} className="text-indigo-400" />
            Video Workspace
          </div>
        </div>

        {loadingState !== 'idle' ? (
          <div
            className="flex flex-col items-center gap-6 p-8 rounded-3xl bg-slate-900/50 backdrop-blur-sm border border-slate-800/50 shadow-2xl relative z-10"
            data-testid="video-main-loading-skeleton"
          >
            <div className="relative">
              <div className="w-24 h-24 border-4 border-indigo-500/30 border-t-indigo-500 rounded-full animate-spin" />
              <div className="absolute inset-0 flex items-center justify-center text-sm font-mono text-indigo-400 font-bold tracking-widest">
                VEO
              </div>
            </div>
            <div className="text-center">
              <p className="text-slate-200 font-medium text-lg">生成中...</p>
              <p className="text-slate-500 text-xs mt-1">视频生成通常会比图片更久一些。</p>
            </div>
          </div>
        ) : isBatchError ? (
          <div className="flex flex-col items-center gap-4 text-center p-8 bg-slate-900/50 rounded-2xl border border-red-900/30 relative z-10">
            <AlertCircle size={48} className="text-red-500 opacity-80" />
            <div>
              <h3 className="text-lg font-bold text-slate-200">生成失败</h3>
              <p className="text-sm text-red-400 mt-2 max-w-md">
                {activeBatchMessage?.content || '未知错误'}
              </p>
            </div>
          </div>
        ) : activeVideoUrl ? (
          <div
            ref={activeVideoStageRef}
            data-testid="video-main-stage"
            className="relative w-full max-w-5xl rounded-[28px] bg-slate-900/80 backdrop-blur-sm border border-slate-800/60 shadow-2xl overflow-hidden z-10"
          >
            <div className="relative group aspect-video bg-black flex items-center justify-center">
              <video
                ref={activeVideoRef}
                data-testid="video-main-player"
                src={activeVideoUrl}
                autoPlay
                loop
                playsInline
                preload="metadata"
                className="h-full w-full object-contain shadow-2xl"
                onClick={() => {
                  void toggleActiveVideoPlayback();
                }}
                onDoubleClick={() => {
                  void handleToggleFullscreen();
                }}
                onPlay={() => setIsVideoPlaying(true)}
                onPause={() => {
                  setIsVideoPlaying(false);
                  const video = activeVideoRef.current;
                  if (video) {
                    syncVideoProgressUi(video.currentTime || 0, video.duration || 0);
                  }
                }}
                onLoadedMetadata={(event) => {
                  const nextDuration = event.currentTarget.duration || 0;
                  setVideoDuration(nextDuration);
                  Array.from(event.currentTarget.textTracks || []).forEach((track, index) => {
                    track.mode = index === 0 ? 'showing' : 'disabled';
                  });
                  syncVideoProgressUi(event.currentTarget.currentTime || 0, nextDuration);
                }}
                onDurationChange={(event) => {
                  const nextDuration = event.currentTarget.duration || 0;
                  setVideoDuration(nextDuration);
                  syncVideoProgressUi(event.currentTarget.currentTime || 0, nextDuration);
                }}
                onEnded={() => {
                  setIsVideoPlaying(false);
                  syncVideoProgressUi(0, videoDuration);
                }}
              >
                {activeSubtitleTrack?.url && (
                  <track
                    key={activeSubtitleTrack.id}
                    src={activeSubtitleTrack.url}
                    kind="captions"
                    srcLang={(activeSubtitleTrack.language || 'zh-CN').split('-')[0]}
                    label={activeSubtitleTrack.language || '字幕'}
                    default
                  />
                )}
              </video>

              <div className="pointer-events-none absolute inset-0 bg-gradient-to-t from-black/70 via-black/15 to-black/40 opacity-0 transition-opacity duration-200 group-hover:opacity-100" />

              <button
                type="button"
                onClick={() => {
                  void toggleActiveVideoPlayback();
                }}
                className="absolute inset-0 z-10 flex items-center justify-center"
                aria-label={isVideoPlaying ? '暂停视频' : '播放视频'}
                title={isVideoPlaying ? '暂停视频' : '播放视频'}
              >
                <span
                  className={`inline-flex h-16 w-16 items-center justify-center rounded-full border border-white/15 bg-black/55 text-white shadow-2xl backdrop-blur-md transition-all duration-200 ${
                    isVideoPlaying
                      ? 'opacity-0 scale-90 group-hover:opacity-100 group-hover:scale-100'
                      : 'opacity-100'
                  }`}
                >
                  {isVideoPlaying ? (
                    <Pause size={28} />
                  ) : (
                    <Play size={28} className="translate-x-0.5" />
                  )}
                </span>
              </button>
            </div>

            <div className="border-t border-slate-800/70 px-5 py-4 bg-slate-950/90">
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => {
                    void toggleActiveVideoPlayback();
                  }}
                  className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-slate-700 bg-slate-900 text-slate-100 hover:border-slate-500 hover:bg-slate-800 transition-colors"
                  title={isVideoPlaying ? '暂停视频' : '播放视频'}
                  aria-label={isVideoPlaying ? '暂停视频' : '播放视频'}
                >
                  {isVideoPlaying ? (
                    <Pause size={18} />
                  ) : (
                    <Play size={18} className="translate-x-0.5" />
                  )}
                </button>
                <span
                  ref={videoCurrentTimeLabelRef}
                  className="w-[76px] text-right font-mono text-xs text-slate-400 tabular-nums"
                >
                  0:00.000
                </span>
                <div className="relative flex-1 h-8 flex items-center">
                  <div className="absolute inset-x-0 top-1/2 -translate-y-1/2 h-1.5 rounded-full bg-slate-800" />
                  <div
                    ref={videoProgressFillRef}
                    className="absolute left-0 top-1/2 -translate-y-1/2 h-1.5 rounded-full bg-gradient-to-r from-indigo-500 to-cyan-400"
                    style={{ width: '0%' }}
                  />
                  <div
                    ref={videoProgressThumbRef}
                    className="absolute top-1/2 h-3.5 w-3.5 -translate-x-1/2 -translate-y-1/2 rounded-full border border-white/60 bg-white shadow-[0_0_0_4px_rgba(99,102,241,0.18)] pointer-events-none"
                    style={{ left: '0%' }}
                  />
                  <input
                    ref={videoSeekInputRef}
                    type="range"
                    min={0}
                    max={Math.max(videoDuration, 0.001)}
                    step="any"
                    defaultValue={0}
                    onChange={handleActiveVideoSeek}
                    className="relative z-10 h-8 w-full cursor-pointer opacity-0"
                    aria-label="视频进度"
                  />
                </div>
                <span className="w-[76px] font-mono text-xs text-slate-400 tabular-nums">
                  {formatVideoTime(videoDuration)}
                </span>
                <div className="mx-1 h-5 w-px bg-slate-800" />
                <button
                  type="button"
                  onClick={handleToggleMute}
                  className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-slate-700 bg-slate-900 text-slate-100 hover:border-slate-500 hover:bg-slate-800 transition-colors"
                  title={isVideoMuted || videoVolume <= 0.001 ? '取消静音' : '静音'}
                  aria-label={isVideoMuted || videoVolume <= 0.001 ? '取消静音' : '静音'}
                >
                  {isVideoMuted || videoVolume <= 0.001 ? (
                    <VolumeX size={18} />
                  ) : (
                    <Volume2 size={18} />
                  )}
                </button>
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.01}
                  value={isVideoMuted ? 0 : videoVolume}
                  onChange={handleActiveVideoVolumeChange}
                  className="w-24 accent-indigo-500"
                  aria-label="视频音量"
                />
                <button
                  type="button"
                  onClick={() => {
                    void handleToggleFullscreen();
                  }}
                  className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-slate-700 bg-slate-900 text-slate-100 hover:border-slate-500 hover:bg-slate-800 transition-colors"
                  title={isVideoFullscreen ? '退出全屏' : '全屏播放'}
                  aria-label={isVideoFullscreen ? '退出全屏' : '全屏播放'}
                >
                  <Maximize2 size={18} />
                </button>
                <button
                  type="button"
                  onClick={() => handleDownload(activeVideoUrl)}
                  className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-indigo-500/30 bg-indigo-600 text-white hover:bg-indigo-500 transition-colors shadow-lg"
                  title="下载视频"
                  aria-label="下载视频"
                >
                  <Download size={18} />
                </button>
                {downloadableSubtitleAttachment?.url && (
                  <button
                    type="button"
                    onClick={() => handleDownload(downloadableSubtitleAttachment.url!)}
                    className="inline-flex h-10 items-center justify-center rounded-xl border border-slate-700 bg-slate-900 px-3 text-xs text-slate-100 hover:border-slate-500 hover:bg-slate-800 transition-colors"
                    title="下载字幕文件"
                    aria-label="下载字幕文件"
                  >
                    字幕
                  </button>
                )}
              </div>
            </div>
          </div>
        ) : (
          <div className="text-center text-slate-600 flex flex-col items-center gap-6 relative z-10">
            <div className="w-32 h-32 rounded-3xl bg-slate-900 border border-slate-800 flex items-center justify-center shadow-inner relative overflow-hidden group">
              <div className="absolute inset-0 bg-gradient-to-tr from-indigo-500/10 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
              <VideoIcon
                size={64}
                className="opacity-20 group-hover:scale-110 transition-transform duration-500"
              />
            </div>
            <div>
              <h3 className="text-2xl font-bold text-slate-500 mb-2">Video Generator</h3>
              <p className="max-w-xs mx-auto text-sm opacity-60">
                Describe a scene, or upload an image to animate using Google Veo.
              </p>
            </div>
          </div>
        )}
      </div>

      <ViewSideParamsPanel
        title="视频参数"
        iconClass="text-indigo-400"
        resetParams={resetParams}
        controlsContent={
          <ModeControlsCoordinator
            mode={videoMode}
            providerId={resolvedProviderId}
            currentModel={activeModelConfig}
            controls={controls}
          />
        }
        editAreaContent={
          <ChatEditInputArea
            onSend={handleSend}
            isLoading={loadingState !== 'idle'}
            onStop={onStop}
            mode={videoMode}
            activeAttachments={activeAttachments}
            onAttachmentsChange={setActiveAttachments}
            activeImageUrl={activeImageUrl}
            onActiveImageUrlChange={setActiveImageUrl}
            messages={messages}
            sessionId={sessionId ?? null}
            initialPrompt={initialPrompt}
            providerId={resolvedProviderId}
            controls={controls}
            externalDisabled={Boolean(videoControlsStatusMessage)}
            externalDisabledReason={videoControlsStatusMessage}
          />
        }
      />
    </div>
  );
};
