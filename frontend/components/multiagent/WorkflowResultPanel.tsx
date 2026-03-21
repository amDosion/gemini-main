import React from 'react';
import { AlertTriangle, ChevronLeft, ChevronRight, Copy, X } from 'lucide-react';
import {
  isDirectlyRenderableAudioUrl,
  isDirectlyRenderableImageUrl,
  isDirectlyRenderableVideoUrl,
  isLocalFilesystemPath,
} from './workflowResultUtils';

export interface RenderedWorkflowResultItem {
  key: string;
  title: string;
  text: string;
  imageUrls: string[];
  audioUrls: string[];
  videoUrls: string[];
  urls: string[];
  thoughts: string[];
}

interface WorkflowResultPanelProps {
  show: boolean;
  executionId: string;
  finalCompletedAt: number | null;
  finalRuntime: string;
  finalRuntimeHints: string[];
  finalError: string | null;
  finalResult: unknown;
  renderedResultItems: RenderedWorkflowResultItem[];
  finalOutputImageUrls: string[];
  finalOutputAudioUrls: string[];
  finalOutputVideoUrls: string[];
  renderableSourceInputPreviewUrl: string | null;
  resultPanelPreviewLoadingExecutionId: string | null;
  onBatchDownloadImages: () => void;
  onBatchDownloadAudio: () => void;
  onBatchDownloadVideo: () => void;
  onCopyResult: () => void;
  onClose: () => void;
  onRetryResultPreview: () => void;
}

export const WorkflowResultPanel: React.FC<WorkflowResultPanelProps> = ({
  show,
  executionId,
  finalCompletedAt,
  finalRuntime,
  finalRuntimeHints,
  finalError,
  finalResult,
  renderedResultItems,
  finalOutputImageUrls,
  finalOutputAudioUrls,
  finalOutputVideoUrls,
  renderableSourceInputPreviewUrl,
  resultPanelPreviewLoadingExecutionId,
  onBatchDownloadImages,
  onBatchDownloadAudio,
  onBatchDownloadVideo,
  onCopyResult,
  onClose,
  onRetryResultPreview,
}) => {
  const videoResultMetadata = React.useMemo(() => {
    const candidates: Record<string, any>[] = [];
    if (finalResult && typeof finalResult === 'object') {
      candidates.push(finalResult);
      if (finalResult.finalOutput && typeof finalResult.finalOutput === 'object') {
        candidates.push(finalResult.finalOutput);
      }
    }

    const summary = {
      continuationStrategy: '',
      videoExtensionCount: 0,
      videoExtensionApplied: 0,
      totalDurationSeconds: 0,
      continuedFromVideo: false,
      subtitleMode: 'none',
      subtitleFileCount: 0,
    };

    for (const candidate of candidates) {
      const continuationStrategy = String(
        candidate.continuationStrategy ?? candidate.continuation_strategy ?? ''
      ).trim();
      if (continuationStrategy && !summary.continuationStrategy) {
        summary.continuationStrategy = continuationStrategy;
      }

      const extensionCount = Number(candidate.videoExtensionCount ?? candidate.video_extension_count ?? 0) || 0;
      const extensionApplied = Number(candidate.videoExtensionApplied ?? candidate.video_extension_applied ?? 0) || 0;
      const totalDurationSeconds = Number(candidate.totalDurationSeconds ?? candidate.total_duration_seconds ?? 0) || 0;
      const subtitleMode = String(candidate.subtitleMode ?? candidate.subtitle_mode ?? '').trim().toLowerCase();
      const subtitleFileCount = Number(candidate.subtitleFileCount ?? candidate.subtitle_file_count ?? 0) || 0;

      summary.videoExtensionCount = Math.max(summary.videoExtensionCount, extensionCount);
      summary.videoExtensionApplied = Math.max(summary.videoExtensionApplied, extensionApplied);
      summary.totalDurationSeconds = Math.max(summary.totalDurationSeconds, totalDurationSeconds);
      summary.subtitleFileCount = Math.max(summary.subtitleFileCount, subtitleFileCount);
      summary.continuedFromVideo = summary.continuedFromVideo || Boolean(candidate.continuedFromVideo ?? candidate.continued_from_video ?? false);
      if (subtitleMode && (subtitleMode !== 'none' || summary.subtitleMode === 'none')) {
        summary.subtitleMode = subtitleMode;
      }
    }

    return summary;
  }, [finalResult]);
  const renderableFinalOutputImageUrls = React.useMemo(
    () => finalOutputImageUrls.filter((imageUrl) => isDirectlyRenderableImageUrl(imageUrl)),
    [finalOutputImageUrls]
  );
  const renderableFinalOutputAudioUrls = React.useMemo(
    () => finalOutputAudioUrls.filter((audioUrl) => isDirectlyRenderableAudioUrl(audioUrl)),
    [finalOutputAudioUrls]
  );
  const renderableFinalOutputVideoUrls = React.useMemo(
    () => finalOutputVideoUrls.filter((videoUrl) => isDirectlyRenderableVideoUrl(videoUrl)),
    [finalOutputVideoUrls]
  );
  const hasRenderableResultMedia = (
    renderableFinalOutputImageUrls.length > 0
    || renderableFinalOutputAudioUrls.length > 0
    || renderableFinalOutputVideoUrls.length > 0
  );
  const [lightboxState, setLightboxState] = React.useState<{ images: string[]; index: number } | null>(null);
  const openImageLightbox = React.useCallback((images: string[], index: number) => {
    const renderableImages = images.filter((imageUrl) => isDirectlyRenderableImageUrl(imageUrl));
    if (renderableImages.length === 0) {
      return;
    }
    const normalizedIndex = Math.max(0, Math.min(renderableImages.length - 1, Number(index) || 0));
    setLightboxState({
      images: renderableImages,
      index: normalizedIndex,
    });
  }, []);
  const closeImageLightbox = React.useCallback(() => {
    setLightboxState(null);
  }, []);
  const activeLightboxImages = lightboxState?.images || [];
  const activeLightboxIndex = lightboxState ? Math.max(0, Math.min(activeLightboxImages.length - 1, lightboxState.index)) : 0;
  const activeLightboxImageUrl = activeLightboxImages[activeLightboxIndex] || '';
  const canNavigateLightbox = activeLightboxImages.length > 1;
  const showPrevLightboxImage = React.useCallback(() => {
    setLightboxState((prev) => {
      if (!prev || prev.images.length <= 1) return prev;
      const nextIndex = (prev.index - 1 + prev.images.length) % prev.images.length;
      return { ...prev, index: nextIndex };
    });
  }, []);
  const showNextLightboxImage = React.useCallback(() => {
    setLightboxState((prev) => {
      if (!prev || prev.images.length <= 1) return prev;
      const nextIndex = (prev.index + 1) % prev.images.length;
      return { ...prev, index: nextIndex };
    });
  }, []);

  React.useEffect(() => {
    if (!show) {
      setLightboxState(null);
    }
  }, [show]);

  React.useEffect(() => {
    if (!lightboxState) return;
    const handleKeydown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        event.preventDefault();
        closeImageLightbox();
        return;
      }
      if (event.key === 'ArrowLeft') {
        event.preventDefault();
        showPrevLightboxImage();
        return;
      }
      if (event.key === 'ArrowRight') {
        event.preventDefault();
        showNextLightboxImage();
      }
    };
    window.addEventListener('keydown', handleKeydown);
    return () => {
      window.removeEventListener('keydown', handleKeydown);
    };
  }, [lightboxState, closeImageLightbox, showPrevLightboxImage, showNextLightboxImage]);

  if (!show) return null;

  return (
    <div className="absolute top-0 right-0 h-full w-[min(58vw,820px)] max-w-[94vw] sm:min-w-[560px] bg-slate-900 border-l border-slate-700 shadow-2xl z-20 flex flex-col">
      <div className="px-4 py-3 border-b border-slate-700 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-slate-100">最终结果</h3>
          <p className="text-[11px] text-slate-400 mt-0.5">
            {finalCompletedAt ? `完成时间：${new Date(finalCompletedAt).toLocaleString()}` : '等待工作流执行完成'}
          </p>
          {finalRuntime && (
            <div className="mt-1 inline-flex items-center text-[10px] px-1.5 py-0.5 rounded border border-amber-500/30 bg-amber-500/10 text-amber-200">
              runtime: {finalRuntime}
            </div>
          )}
          {!finalRuntime && finalRuntimeHints.length > 0 && (
            <div className="mt-1 flex flex-wrap gap-1">
              {finalRuntimeHints.map((hint) => (
                <span
                  key={`runtime-hint-${hint}`}
                  className="inline-flex items-center text-[10px] px-1.5 py-0.5 rounded border border-amber-500/20 bg-amber-500/5 text-amber-100/90"
                >
                  runtime: {hint}
                </span>
              ))}
            </div>
          )}
          {(videoResultMetadata.videoExtensionApplied > 0
            || videoResultMetadata.videoExtensionCount > 0
            || videoResultMetadata.totalDurationSeconds > 0
            || videoResultMetadata.subtitleMode !== 'none'
            || videoResultMetadata.subtitleFileCount > 0
            || videoResultMetadata.continuedFromVideo
            || Boolean(videoResultMetadata.continuationStrategy)) && (
            <div className="mt-1 flex flex-wrap gap-1">
              {(videoResultMetadata.videoExtensionApplied > 0 || videoResultMetadata.videoExtensionCount > 0) && (
                <span className="inline-flex items-center text-[10px] px-1.5 py-0.5 rounded border border-orange-500/30 bg-orange-500/10 text-orange-200">
                  延长 {videoResultMetadata.videoExtensionApplied || videoResultMetadata.videoExtensionCount} 次
                </span>
              )}
              {videoResultMetadata.totalDurationSeconds > 0 && (
                <span className="inline-flex items-center text-[10px] px-1.5 py-0.5 rounded border border-cyan-500/30 bg-cyan-500/10 text-cyan-200">
                  总时长 {videoResultMetadata.totalDurationSeconds}s
                </span>
              )}
              {(videoResultMetadata.subtitleMode !== 'none' || videoResultMetadata.subtitleFileCount > 0) && (
                <span className="inline-flex items-center text-[10px] px-1.5 py-0.5 rounded border border-emerald-500/30 bg-emerald-500/10 text-emerald-200">
                  字幕{videoResultMetadata.subtitleFileCount > 0 ? ` · ${videoResultMetadata.subtitleFileCount}` : ''}
                </span>
              )}
              {(videoResultMetadata.continuedFromVideo || videoResultMetadata.continuationStrategy) && (
                <span className="inline-flex items-center text-[10px] px-1.5 py-0.5 rounded border border-violet-500/30 bg-violet-500/10 text-violet-200">
                  {videoResultMetadata.continuationStrategy === 'video_extension_chain' ? '官方续接' : '视频续接'}
                </span>
              )}
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          {renderableFinalOutputImageUrls.length > 0 && (
            <button
              onClick={onBatchDownloadImages}
              className="px-2 py-1.5 rounded border border-slate-600 bg-slate-800 hover:bg-slate-700 text-[11px] text-slate-300 transition-colors"
              title={`批量下载 ${renderableFinalOutputImageUrls.length} 张图片`}
            >
              图 {renderableFinalOutputImageUrls.length}
            </button>
          )}
          {renderableFinalOutputVideoUrls.length > 0 && (
            <button
              onClick={onBatchDownloadVideo}
              className="px-2 py-1.5 rounded border border-slate-600 bg-slate-800 hover:bg-slate-700 text-[11px] text-slate-300 transition-colors"
              title={`批量下载 ${renderableFinalOutputVideoUrls.length} 条视频`}
            >
              视 {renderableFinalOutputVideoUrls.length}
            </button>
          )}
          {renderableFinalOutputAudioUrls.length > 0 && (
            <button
              onClick={onBatchDownloadAudio}
              className="px-2 py-1.5 rounded border border-slate-600 bg-slate-800 hover:bg-slate-700 text-[11px] text-slate-300 transition-colors"
              title={`批量下载 ${renderableFinalOutputAudioUrls.length} 条音频`}
            >
              音 {renderableFinalOutputAudioUrls.length}
            </button>
          )}
          <button
            onClick={onCopyResult}
            className="p-1.5 rounded border border-slate-600 bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
            title="复制结果"
          >
            <Copy size={14} />
          </button>
          <button
            onClick={onClose}
            className="p-1.5 rounded border border-slate-600 bg-slate-800 hover:bg-slate-700 text-slate-300 transition-colors"
            title="关闭结果面板"
          >
            <X size={14} />
          </button>
        </div>
      </div>
      <div className="flex-1 overflow-auto p-4 space-y-3">
        {finalError && (
          <div className="p-3 rounded-lg border border-rose-500/30 bg-rose-500/10 text-rose-200 text-xs flex items-start gap-2">
            <AlertTriangle size={14} className="mt-0.5 flex-shrink-0" />
            <span>{finalError}</span>
          </div>
        )}
        {(renderableSourceInputPreviewUrl || renderableFinalOutputImageUrls.length > 0) && (
          <div className="rounded-lg border border-indigo-500/30 bg-indigo-500/10 p-3 space-y-2">
            <div className="text-xs font-semibold text-indigo-200">输入/输出对照</div>
            <div className="grid grid-cols-2 gap-2">
              <div>
                <div className="text-[11px] text-slate-400 mb-1">输入原图</div>
                {renderableSourceInputPreviewUrl ? (
                  <img
                    src={renderableSourceInputPreviewUrl}
                    alt="workflow-input-image"
                    className="w-full rounded border border-slate-700 object-contain max-h-[180px] bg-slate-900"
                  />
                ) : (
                  <div className="h-[120px] rounded border border-dashed border-slate-700 bg-slate-900/50 text-[11px] text-slate-500 flex items-center justify-center">
                    未提供输入图片
                  </div>
                )}
              </div>
              <div>
                <div className="text-[11px] text-slate-400 mb-1">生成结果</div>
                {renderableFinalOutputImageUrls.length > 0 ? (
                  <div className="space-y-1.5">
                    <div className="text-[11px] text-slate-400">全部输出（{renderableFinalOutputImageUrls.length}）</div>
                    <div className="grid grid-cols-4 gap-1.5 max-h-[180px] overflow-y-auto pr-0.5">
                    {renderableFinalOutputImageUrls.map((imageUrl, index) => (
                      <button
                        type="button"
                        key={`workflow-output-image-${index + 1}`}
                        onClick={() => openImageLightbox(renderableFinalOutputImageUrls, index)}
                        className="w-full h-16 rounded border border-slate-700 bg-slate-900 overflow-hidden hover:border-indigo-400 transition-colors"
                      >
                        <img
                          src={imageUrl}
                          alt="workflow-output-image"
                          className="w-full h-full object-cover"
                          loading="lazy"
                        />
                      </button>
                    ))}
                    </div>
                  </div>
                ) : (
                  <div className="h-[120px] rounded border border-dashed border-slate-700 bg-slate-900/50 text-[11px] text-slate-500 flex items-center justify-center">
                    暂无输出图片
                  </div>
                )}
              </div>
            </div>
            {resultPanelPreviewLoadingExecutionId === executionId && renderableFinalOutputImageUrls.length === 0 && (
              <div className="text-[11px] text-slate-400">正在加载结果媒体预览...</div>
            )}
            {resultPanelPreviewLoadingExecutionId !== executionId && renderableFinalOutputImageUrls.length === 0 && executionId && (
              <button
                type="button"
                onClick={onRetryResultPreview}
                className="text-[11px] text-indigo-200 hover:text-indigo-100 underline decoration-dotted underline-offset-2"
              >
                重试加载结果媒体
              </button>
            )}
            {renderableFinalOutputImageUrls.length > 1 && (
              <div className="text-[11px] text-slate-400">
                点击图片可放大查看（支持键盘左右键切换）
              </div>
            )}
          </div>
        )}
        {(renderableFinalOutputVideoUrls.length > 0 || renderableFinalOutputAudioUrls.length > 0) && (
          <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/5 p-3 space-y-3">
            <div className="text-xs font-semibold text-emerald-200">媒体结果</div>
            {renderableFinalOutputVideoUrls.length > 0 && (
              <div className="space-y-2">
                <div className="text-[11px] text-slate-400">视频结果（{renderableFinalOutputVideoUrls.length}）</div>
                <div className="space-y-3">
                  {renderableFinalOutputVideoUrls.map((videoUrl, index) => (
                    <div key={`final-video-${index}`} className="overflow-hidden rounded-xl border border-slate-700 bg-slate-950/80">
                      <div className="flex items-center justify-between gap-2 border-b border-slate-800 px-3 py-2">
                        <div className="text-[11px] font-medium text-slate-200">视频 {index + 1}</div>
                        <div className="text-[10px] text-slate-500">结果预览</div>
                      </div>
                      <video
                        src={videoUrl}
                        controls
                        preload="metadata"
                        className="aspect-video w-full bg-black"
                      />
                    </div>
                  ))}
                </div>
              </div>
            )}
            {renderableFinalOutputAudioUrls.length > 0 && (
              <div className="space-y-2">
                <div className="text-[11px] text-slate-400">音频结果（{renderableFinalOutputAudioUrls.length}）</div>
                <div className="space-y-2">
                  {renderableFinalOutputAudioUrls.map((audioUrl, index) => (
                    <div key={`final-audio-${index}`} className="rounded border border-slate-700 bg-slate-950/80 p-2">
                      <audio src={audioUrl} controls className="w-full" />
                    </div>
                  ))}
                </div>
              </div>
            )}
            {resultPanelPreviewLoadingExecutionId === executionId && !hasRenderableResultMedia && (
              <div className="text-[11px] text-slate-400">正在加载结果媒体预览...</div>
            )}
          </div>
        )}
        {resultPanelPreviewLoadingExecutionId !== executionId
          && !hasRenderableResultMedia
          && executionId
          && finalResult !== null
          && !(renderableSourceInputPreviewUrl || renderableFinalOutputImageUrls.length > 0) && (
          <button
            type="button"
            onClick={onRetryResultPreview}
            className="text-[11px] text-indigo-200 hover:text-indigo-100 underline decoration-dotted underline-offset-2"
          >
            重试加载结果媒体
          </button>
        )}
        {!finalError && finalResult === null && (
          <div className="h-full flex items-center justify-center text-xs text-slate-500">
            暂无结果，请先执行工作流
          </div>
        )}
        {finalResult !== null && renderedResultItems.length > 0 && (
          <div className="space-y-3">
            {renderedResultItems.map((item) => (
              <div key={item.key} className="rounded-lg border border-slate-700 bg-slate-950/80 p-3 space-y-2">
                <div className="text-xs font-semibold text-slate-200">{item.title}</div>
                {item.text && (
                  <div className="text-xs text-slate-300 whitespace-pre-wrap break-words leading-relaxed">
                    {item.text}
                  </div>
                )}
                {item.thoughts.length > 0 && (
                  <div className="rounded border border-cyan-500/20 bg-cyan-500/5 p-2 space-y-1">
                    <div className="text-[11px] font-medium text-cyan-200">思考摘要</div>
                    {item.thoughts.map((thought, index) => (
                      <div
                        key={`${item.key}-thought-${index}`}
                        className="text-[11px] text-cyan-50/90 whitespace-pre-wrap break-words leading-relaxed"
                      >
                        {thought}
                      </div>
                    ))}
                  </div>
                )}
                {item.urls.length > 0 && (
                  <div className="rounded border border-slate-700 bg-slate-900/50 p-2 space-y-1">
                    <div className="text-[11px] font-medium text-slate-300">返回 URL ({item.urls.length})</div>
                    {item.urls.map((url, index) => {
                      const isLink = /^(https?:\/\/)/i.test(url) || (url.startsWith('/') && !isLocalFilesystemPath(url));
                      if (isLink) {
                        return (
                          <a
                            key={`${item.key}-url-${index}`}
                            href={url}
                            target={/^https?:\/\//i.test(url) ? '_blank' : undefined}
                            rel={/^https?:\/\//i.test(url) ? 'noreferrer' : undefined}
                            className="block text-[11px] text-sky-300 hover:text-sky-200 underline decoration-dotted break-all"
                          >
                            {url}
                          </a>
                        );
                      }
                      return (
                        <div
                          key={`${item.key}-url-${index}`}
                          className="text-[11px] text-slate-400 break-all"
                        >
                          {url}
                        </div>
                      );
                    })}
                  </div>
                )}
                {item.imageUrls.length > 0 && (
                  <div className="space-y-2">
                    <div className="text-[11px] text-slate-400">图片结果（{item.imageUrls.filter((imageUrl) => isDirectlyRenderableImageUrl(imageUrl)).length}）</div>
                    <div className="grid grid-cols-4 gap-1.5">
                      {item.imageUrls
                        .filter((imageUrl) => isDirectlyRenderableImageUrl(imageUrl))
                        .map((imageUrl, index, imageList) => (
                          <button
                            type="button"
                            key={`${item.key}-image-${index}`}
                            onClick={() => openImageLightbox(imageList, index)}
                            className="w-full h-16 rounded border border-slate-700 bg-slate-900 overflow-hidden hover:border-indigo-400 transition-colors"
                          >
                            <img
                              src={imageUrl}
                              alt={`${item.title}-${index + 1}`}
                              className="w-full h-full object-cover"
                              loading="lazy"
                            />
                          </button>
                      ))}
                    </div>
                  </div>
                )}
                {item.videoUrls.length > 0 && (
                  <div className="space-y-2">
                    <div className="text-[11px] text-slate-400">视频结果（{item.videoUrls.filter((videoUrl) => isDirectlyRenderableVideoUrl(videoUrl)).length}）</div>
                    <div className="space-y-3">
                      {item.videoUrls
                        .filter((videoUrl) => isDirectlyRenderableVideoUrl(videoUrl))
                        .map((videoUrl, index) => (
                          <div
                            key={`${item.key}-video-${index}`}
                            className="overflow-hidden rounded-xl border border-slate-700 bg-slate-900/50"
                          >
                            <div className="flex items-center justify-between gap-2 border-b border-slate-800 px-3 py-2">
                              <div className="text-[11px] font-medium text-slate-200">{item.title} · 视频 {index + 1}</div>
                              <div className="text-[10px] text-slate-500">节点结果</div>
                            </div>
                            <video
                              src={videoUrl}
                              controls
                              preload="metadata"
                              className="aspect-video w-full bg-slate-950"
                            />
                          </div>
                        ))}
                    </div>
                  </div>
                )}
                {item.audioUrls.length > 0 && (
                  <div className="space-y-2">
                    <div className="text-[11px] text-slate-400">音频结果（{item.audioUrls.filter((audioUrl) => isDirectlyRenderableAudioUrl(audioUrl)).length}）</div>
                    <div className="space-y-2">
                      {item.audioUrls
                        .filter((audioUrl) => isDirectlyRenderableAudioUrl(audioUrl))
                        .map((audioUrl, index) => (
                          <div
                            key={`${item.key}-audio-${index}`}
                            className="rounded border border-slate-700 bg-slate-900/50 p-2"
                          >
                            <audio src={audioUrl} controls className="w-full" />
                          </div>
                        ))}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
      {lightboxState && activeLightboxImageUrl && (
        <div
          className="fixed inset-0 z-[70] bg-black/90 flex items-center justify-center px-6 py-8"
          onClick={closeImageLightbox}
        >
          <div className="relative w-full h-full max-w-6xl flex items-center justify-center" onClick={(event) => event.stopPropagation()}>
            {canNavigateLightbox && (
              <button
                type="button"
                onClick={showPrevLightboxImage}
                className="absolute left-2 top-1/2 -translate-y-1/2 p-2 rounded-full border border-slate-600 bg-slate-900/80 text-slate-100 hover:bg-slate-800 transition-colors"
                title="上一张（←）"
              >
                <ChevronLeft size={20} />
              </button>
            )}
            <img
              src={activeLightboxImageUrl}
              alt={`preview-${activeLightboxIndex + 1}`}
              className="max-w-full max-h-full object-contain rounded border border-slate-700 bg-slate-950"
            />
            {canNavigateLightbox && (
              <button
                type="button"
                onClick={showNextLightboxImage}
                className="absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-full border border-slate-600 bg-slate-900/80 text-slate-100 hover:bg-slate-800 transition-colors"
                title="下一张（→）"
              >
                <ChevronRight size={20} />
              </button>
            )}
            <button
              type="button"
              onClick={closeImageLightbox}
              className="absolute top-2 right-2 p-2 rounded-full border border-slate-600 bg-slate-900/80 text-slate-100 hover:bg-slate-800 transition-colors"
              title="关闭（Esc）"
            >
              <X size={18} />
            </button>
            <div className="absolute bottom-2 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full border border-slate-600 bg-slate-900/80 text-xs text-slate-200">
              {activeLightboxIndex + 1} / {activeLightboxImages.length}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
