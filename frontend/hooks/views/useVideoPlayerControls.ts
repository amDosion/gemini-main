/**
 * 视频播放器控制 hook（自定义 controls 条 + 全屏 + 音量 + seek + rAF 进度同步）。
 *
 * 1:1 抽离自 `VideoGenView.tsx` L121-132 (state/refs) + L540-661 (handlers)
 * （JIRA-frontend-deep-architecture-split.md #3 Step 1）。
 *
 * 设计：state setters 引用稳定，refs 非反应式 → useCallback deps 仅必要项。
 */

import { useCallback, useRef, useState } from 'react';

export interface UseVideoPlayerControlsResult {
  // State
  isVideoPlaying: boolean;
  setIsVideoPlaying: React.Dispatch<React.SetStateAction<boolean>>;
  videoDuration: number;
  setVideoDuration: React.Dispatch<React.SetStateAction<number>>;
  isVideoFullscreen: boolean;
  setIsVideoFullscreen: React.Dispatch<React.SetStateAction<boolean>>;
  videoVolume: number;
  isVideoMuted: boolean;
  // Refs
  activeVideoRef: React.MutableRefObject<HTMLVideoElement | null>;
  activeVideoStageRef: React.MutableRefObject<HTMLDivElement | null>;
  videoSeekInputRef: React.MutableRefObject<HTMLInputElement | null>;
  videoProgressFillRef: React.MutableRefObject<HTMLDivElement | null>;
  videoProgressThumbRef: React.MutableRefObject<HTMLDivElement | null>;
  videoCurrentTimeLabelRef: React.MutableRefObject<HTMLSpanElement | null>;
  videoProgressAnimationFrameRef: React.MutableRefObject<number | null>;
  // Handlers
  handleToggleFullscreen: () => Promise<void>;
  formatVideoTime: (timeInSeconds: number) => string;
  handleActiveVideoSeek: (event: React.ChangeEvent<HTMLInputElement>) => void;
  handleActiveVideoVolumeChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
  handleToggleMute: () => void;
  stopVideoProgressAnimation: () => void;
  syncVideoProgressUi: (currentTime: number, duration: number) => void;
  startVideoProgressAnimation: () => void;
}

export const useVideoPlayerControls = (): UseVideoPlayerControlsResult => {
  const activeVideoRef = useRef<HTMLVideoElement | null>(null);
  const activeVideoStageRef = useRef<HTMLDivElement | null>(null);
  const videoProgressAnimationFrameRef = useRef<number | null>(null);
  const videoSeekInputRef = useRef<HTMLInputElement | null>(null);
  const videoProgressFillRef = useRef<HTMLDivElement | null>(null);
  const videoProgressThumbRef = useRef<HTMLDivElement | null>(null);
  const videoCurrentTimeLabelRef = useRef<HTMLSpanElement | null>(null);

  const [isVideoPlaying, setIsVideoPlaying] = useState(false);
  const [videoDuration, setVideoDuration] = useState(0);
  const [isVideoFullscreen, setIsVideoFullscreen] = useState(false);
  const [videoVolume, setVideoVolume] = useState(1);
  const [isVideoMuted, setIsVideoMuted] = useState(false);

  const handleToggleFullscreen = useCallback(async () => {
    const target = activeVideoStageRef.current;
    if (!target || typeof document === 'undefined') {
      return;
    }

    const currentFullscreenElement = document.fullscreenElement;
    if (currentFullscreenElement === target) {
      if (typeof document.exitFullscreen === 'function') {
        await document.exitFullscreen();
      }
      return;
    }
    if (typeof target.requestFullscreen === 'function') {
      await target.requestFullscreen();
    }
  }, []);

  const formatVideoTime = useCallback((timeInSeconds: number) => {
    if (!Number.isFinite(timeInSeconds) || timeInSeconds < 0) {
      return '0:00.000';
    }
    const totalMilliseconds = Math.floor(timeInSeconds * 1000);
    const hours = Math.floor(totalMilliseconds / 3_600_000);
    const minutes = Math.floor((totalMilliseconds % 3_600_000) / 60_000);
    const seconds = Math.floor((totalMilliseconds % 60_000) / 1000);
    const milliseconds = totalMilliseconds % 1000;

    if (hours > 0) {
      return `${hours}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}.${String(milliseconds).padStart(3, '0')}`;
    }

    return `${minutes}:${String(seconds).padStart(2, '0')}.${String(milliseconds).padStart(3, '0')}`;
  }, []);

  const handleActiveVideoSeek = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const video = activeVideoRef.current;
      if (!video) {
        return;
      }
      const nextTime = Number(event.target.value);
      video.currentTime = nextTime;
      const duration = video.duration || videoDuration || 0;
      const ratio = duration > 0 ? nextTime / duration : 0;
      if (videoProgressFillRef.current) {
        videoProgressFillRef.current.style.width = `${Math.max(0, Math.min(1, ratio)) * 100}%`;
      }
      if (videoProgressThumbRef.current) {
        videoProgressThumbRef.current.style.left = `${Math.max(0, Math.min(1, ratio)) * 100}%`;
      }
      if (videoCurrentTimeLabelRef.current) {
        videoCurrentTimeLabelRef.current.textContent = formatVideoTime(nextTime);
      }
    },
    [formatVideoTime, videoDuration]
  );

  const handleActiveVideoVolumeChange = useCallback(
    (event: React.ChangeEvent<HTMLInputElement>) => {
      const nextVolume = Number(event.target.value);
      setVideoVolume(nextVolume);
      setIsVideoMuted(nextVolume <= 0.001);
    },
    []
  );

  const handleToggleMute = useCallback(() => {
    setIsVideoMuted((previous) => !previous);
  }, []);

  const stopVideoProgressAnimation = useCallback(() => {
    if (videoProgressAnimationFrameRef.current !== null) {
      window.cancelAnimationFrame(videoProgressAnimationFrameRef.current);
      videoProgressAnimationFrameRef.current = null;
    }
  }, []);

  const syncVideoProgressUi = useCallback(
    (currentTime: number, duration: number) => {
      const safeDuration = Number.isFinite(duration) && duration > 0 ? duration : 0;
      const safeCurrentTime = Number.isFinite(currentTime) && currentTime > 0 ? currentTime : 0;
      const ratio = safeDuration > 0 ? safeCurrentTime / safeDuration : 0;
      const progressPercent = `${Math.max(0, Math.min(1, ratio)) * 100}%`;

      if (videoSeekInputRef.current) {
        videoSeekInputRef.current.value = String(safeCurrentTime);
      }
      if (videoProgressFillRef.current) {
        videoProgressFillRef.current.style.width = progressPercent;
      }
      if (videoProgressThumbRef.current) {
        videoProgressThumbRef.current.style.left = progressPercent;
      }
      if (videoCurrentTimeLabelRef.current) {
        videoCurrentTimeLabelRef.current.textContent = formatVideoTime(safeCurrentTime);
      }
    },
    [formatVideoTime]
  );

  const startVideoProgressAnimation = useCallback(() => {
    stopVideoProgressAnimation();

    const syncProgress = () => {
      const video = activeVideoRef.current;
      if (!video) {
        videoProgressAnimationFrameRef.current = null;
        return;
      }

      syncVideoProgressUi(video.currentTime || 0, video.duration || 0);

      if (!video.paused && !video.ended) {
        videoProgressAnimationFrameRef.current = window.requestAnimationFrame(syncProgress);
      } else {
        videoProgressAnimationFrameRef.current = null;
      }
    };

    videoProgressAnimationFrameRef.current = window.requestAnimationFrame(syncProgress);
  }, [stopVideoProgressAnimation, syncVideoProgressUi]);

  return {
    isVideoPlaying,
    setIsVideoPlaying,
    videoDuration,
    setVideoDuration,
    isVideoFullscreen,
    setIsVideoFullscreen,
    videoVolume,
    isVideoMuted,
    activeVideoRef,
    activeVideoStageRef,
    videoSeekInputRef,
    videoProgressFillRef,
    videoProgressThumbRef,
    videoCurrentTimeLabelRef,
    videoProgressAnimationFrameRef,
    handleToggleFullscreen,
    formatVideoTime,
    handleActiveVideoSeek,
    handleActiveVideoVolumeChange,
    handleToggleMute,
    stopVideoProgressAnimation,
    syncVideoProgressUi,
    startVideoProgressAnimation,
  };
};
