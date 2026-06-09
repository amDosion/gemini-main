import React, { useEffect, useMemo, useState } from 'react';
import { Grid3X3, Images, Loader2, X } from 'lucide-react';

import { ImageResultCanvas } from '../common/ImageResultCanvas';
import type { CarouselMediaItem } from '../common/ImageCarouselControls';
import { CachedImage } from '../common/CachedImage';
import { useImageCanvas } from '../../hooks/useImageCanvas';
import { useImageCarousel } from '../../hooks/useImageCarousel';
import type { Attachment } from '../../types/types';
import { isDirectlyRenderableImageUrl } from './workflowResultUtils';

export interface WorkflowResultImageCanvasProps {
  open: boolean;
  title?: string;
  imageUrls?: string[];
  imageCards?: WorkflowResultImageCard[];
  totalCount?: number;
  page?: number;
  totalPages?: number;
  onPageChange?: (page: number) => void;
  initialIndex?: number;
  onClose: () => void;
  onImageClick?: (url: string) => void;
}

export type WorkflowResultImageCardLoadState = 'idle' | 'loading' | 'loaded' | 'error';

export interface WorkflowResultImageCard {
  id: string;
  title: string;
  imageUrl?: string;
  executionId?: string;
  imageIndex?: number;
  subtitle?: string;
  indexLabel?: string;
  loadState?: WorkflowResultImageCardLoadState;
}

const normalizeImageUrls = (imageUrls: string[]): string[] => {
  const seen = new Set<string>();
  const normalized: string[] = [];
  imageUrls.forEach((imageUrl) => {
    const value = String(imageUrl || '').trim();
    if (!value || seen.has(value) || !isDirectlyRenderableImageUrl(value)) {
      return;
    }
    seen.add(value);
    normalized.push(value);
  });
  return normalized;
};

export const WorkflowResultImageCanvas: React.FC<WorkflowResultImageCanvasProps> = ({
  open,
  title = '结果图片',
  imageUrls = [],
  imageCards,
  totalCount,
  page = 1,
  totalPages = 1,
  onPageChange,
  initialIndex = 0,
  onClose,
  onImageClick,
}) => {
  const canvas = useImageCanvas({ minZoom: 0.5, maxZoom: 5, initialZoom: 1 });
  const [carouselStartIndex, setCarouselStartIndex] = useState<number | null>(null);
  const normalizedImageUrls = useMemo(() => normalizeImageUrls(imageUrls), [imageUrls]);
  const fallbackCards = useMemo<WorkflowResultImageCard[]>(
    () =>
      normalizedImageUrls.map((url, index) => ({
        id: `workflow-result-image-card-${index}`,
        title: `媒体图片 ${index + 1}`,
        imageUrl: url,
        indexLabel: `${index + 1}/${normalizedImageUrls.length}`,
        loadState: 'loaded',
      })),
    [normalizedImageUrls]
  );
  const displayCards = useMemo<WorkflowResultImageCard[]>(
    () => (Array.isArray(imageCards) && imageCards.length > 0 ? imageCards : fallbackCards),
    [fallbackCards, imageCards]
  );
  const loadedCards = useMemo(
    () =>
      displayCards.filter((card) => card.imageUrl && isDirectlyRenderableImageUrl(card.imageUrl)),
    [displayCards]
  );
  const safeInitialIndex = Number.isFinite(Number(initialIndex)) ? Number(initialIndex) : 0;
  const attachments = useMemo<Attachment[]>(
    () =>
      loadedCards.map((card, index) => ({
        id: `workflow-result-image-${card.id}`,
        name: `workflow-result-${index + 1}.png`,
        mimeType: 'image/png',
        url: card.imageUrl || '',
        kind: 'workflow-result',
      })),
    [loadedCards]
  );
  const carouselItems = useMemo<CarouselMediaItem[]>(
    () =>
      attachments.map((attachment, index) => ({
        id: attachment.id,
        url: attachment.url,
        thumbUrl: attachment.url,
        alt: `结果图片 ${index + 1}`,
      })),
    [attachments]
  );
  const carousel = useImageCarousel({
    itemCount: attachments.length,
    initialIndex: carouselStartIndex ?? safeInitialIndex,
    resetKey: `${open ? 'open' : 'closed'}:${displayCards.map((card) => `${card.id}:${card.imageUrl || card.loadState || ''}`).join('|')}:${carouselStartIndex ?? safeInitialIndex}`,
    keyboardEnabled: open && carouselStartIndex !== null,
  });

  useEffect(() => {
    setCarouselStartIndex(null);
  }, [displayCards, open]);

  if (!open || displayCards.length === 0) {
    return null;
  }

  const isCarouselMode = carouselStartIndex !== null;
  const visibleTotalCount = Math.max(totalCount ?? displayCards.length, displayCards.length);
  const normalizedPage = Math.max(1, Math.floor(Number(page) || 1));
  const normalizedTotalPages = Math.max(1, Math.floor(Number(totalPages) || 1));
  const canPageBackward = Boolean(onPageChange) && normalizedPage > 1;
  const canPageForward = Boolean(onPageChange) && normalizedPage < normalizedTotalPages;
  const openCardInCarousel = (card: WorkflowResultImageCard) => {
    if (!card.imageUrl) {
      return;
    }
    const loadedIndex = loadedCards.findIndex((loadedCard) => loadedCard.id === card.id);
    if (loadedIndex < 0) {
      return;
    }
    setCarouselStartIndex(loadedIndex);
  };

  return (
    <div className="absolute inset-0 z-30 flex flex-col bg-slate-950">
      <div className="flex h-12 shrink-0 items-center justify-between border-b border-slate-800 bg-slate-900/80 px-4">
        <div className="min-w-0 flex items-center gap-2 text-sm font-medium text-slate-200">
          <Images size={16} className="shrink-0 text-indigo-300" />
          <span className="truncate">{title}</span>
          <span className="font-mono text-xs text-slate-500">
            {isCarouselMode
              ? `${carousel.currentNumber} / ${carousel.total}`
              : `${visibleTotalCount} 张`}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {isCarouselMode && (
            <button
              type="button"
              onClick={() => setCarouselStartIndex(null)}
              className="inline-flex h-8 items-center gap-1.5 rounded-lg border border-slate-700 bg-slate-800 px-2.5 text-xs text-slate-300 transition-colors hover:border-indigo-500/40 hover:bg-slate-700 hover:text-indigo-200"
              aria-label="返回图片卡片"
              title="返回图片卡片"
            >
              <Grid3X3 size={14} />
              卡片
            </button>
          )}
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-slate-800 hover:text-slate-100"
            aria-label="关闭图片查看"
            title="返回工作流画布"
          >
            <X size={17} />
          </button>
        </div>
      </div>

      {isCarouselMode && attachments.length > 0 ? (
        <ImageResultCanvas
          loadingState="idle"
          isBatchError={false}
          displayImages={attachments}
          carouselItems={carouselItems}
          carouselIndex={carousel.index}
          handleCarouselPrev={carousel.goPrev}
          handleCarouselNext={carousel.goNext}
          handleCarouselSelect={carousel.select}
          onImageClick={(url) => onImageClick?.(url)}
          altFor={(idx) => `工作流结果图片 ${idx + 1}`}
          canvas={canvas}
          mode="image-gen"
          accentColor="indigo"
          controlsExtra={{
            onFullscreen: () => {
              const currentUrl = attachments[carousel.index]?.url;
              if (currentUrl) {
                onImageClick?.(currentUrl);
              }
            },
          }}
          spinnerColorClass="border-indigo-500/30 border-t-indigo-500"
          spinnerBadgeText="WF"
          spinnerBadgeColorClass="text-indigo-300"
          accentIconClass="text-indigo-300"
          carouselAccentTone="indigo"
          wheelTarget="carousel"
          emptyState={null}
        />
      ) : (
        <div className="min-h-0 flex-1 overflow-y-auto p-5">
          <div className="grid grid-cols-[repeat(auto-fill,minmax(180px,1fr))] gap-4">
            {displayCards.map((card, index) => {
              const isLoaded = Boolean(card.imageUrl);
              const loadState = card.loadState || (isLoaded ? 'loaded' : 'idle');
              const cardTitle = card.title || `媒体图片 ${index + 1}`;
              const indexLabel = card.indexLabel || `${index + 1}/${visibleTotalCount}`;

              return (
                <button
                  type="button"
                  key={card.id}
                  onClick={() => openCardInCarousel(card)}
                  disabled={!isLoaded}
                  className="group overflow-hidden rounded-lg border border-slate-800 bg-slate-900 text-left shadow-lg shadow-black/20 transition-colors hover:border-indigo-500/60 hover:bg-slate-800/80 disabled:cursor-wait disabled:hover:border-slate-800 disabled:hover:bg-slate-900"
                  aria-label={`打开第 ${index + 1} 张媒体图片`}
                  title={isLoaded ? '打开旋转木马查看' : '图片预览加载中'}
                >
                  <div className="aspect-square bg-slate-950">
                    {card.imageUrl ? (
                      <CachedImage
                        source={{
                          id: card.id,
                          name: cardTitle,
                          mimeType: 'image/png',
                          attachmentId: card.id,
                          url: card.imageUrl,
                        }}
                        src={card.imageUrl}
                        alt={`媒体图片 ${index + 1}`}
                        className="h-full w-full object-cover transition-transform duration-200 group-hover:scale-[1.03]"
                        draggable={false}
                      />
                    ) : (
                      <div className="flex h-full w-full flex-col items-center justify-center gap-2 px-3 text-center text-xs text-slate-500">
                        {loadState === 'error' ? (
                          <>
                            <Images size={22} className="text-rose-400" />
                            <span>加载失败</span>
                          </>
                        ) : (
                          <>
                            <Loader2 size={22} className="animate-spin text-indigo-300" />
                            <span>加载中</span>
                          </>
                        )}
                      </div>
                    )}
                  </div>
                  <div className="flex items-center justify-between gap-2 border-t border-slate-800 px-3 py-2">
                    <span className="truncate text-xs font-medium text-slate-300">{cardTitle}</span>
                    <span className="shrink-0 font-mono text-[10px] text-slate-500">
                      {indexLabel}
                    </span>
                  </div>
                  {card.subtitle && (
                    <div className="border-t border-slate-800/70 px-3 py-2 text-[11px] text-slate-500">
                      <div className="truncate">{card.subtitle}</div>
                    </div>
                  )}
                </button>
              );
            })}
          </div>
          {normalizedTotalPages > 1 && (
            <div className="mt-5 flex items-center justify-center gap-3 border-t border-slate-800 pt-4">
              <button
                type="button"
                onClick={() => onPageChange?.(normalizedPage - 1)}
                disabled={!canPageBackward}
                className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs text-slate-300 transition-colors hover:border-indigo-500/50 hover:text-indigo-200 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:border-slate-700 disabled:hover:text-slate-300"
                aria-label="上一页"
              >
                上一页
              </button>
              <span className="font-mono text-xs text-slate-500">
                第 {normalizedPage} / {normalizedTotalPages} 页
              </span>
              <button
                type="button"
                onClick={() => onPageChange?.(normalizedPage + 1)}
                disabled={!canPageForward}
                className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-1.5 text-xs text-slate-300 transition-colors hover:border-indigo-500/50 hover:text-indigo-200 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:border-slate-700 disabled:hover:text-slate-300"
                aria-label="下一页"
              >
                下一页
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default WorkflowResultImageCanvas;
