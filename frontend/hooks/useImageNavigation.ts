
import { useState, useMemo, useCallback } from 'react';
import { Message } from '../types/types';

interface UseImageNavigationReturn {
  previewImage: string | null;
  setPreviewImage: (url: string | null) => void;
  allImages: string[];
  currentImageIndex: number;
  handleNextImage: () => void;
  handlePrevImage: () => void;
  handleImageClick: (url: string) => void;
}

/**
 * 图片导航 Hook
 * 管理图片预览、导航和索引
 */
export const useImageNavigation = (messages: Message[]): UseImageNavigationReturn => {
  const [previewImage, setPreviewImage] = useState<string | null>(null);

  // 计算所有图片和当前索引
  const { allImages, currentImageIndex } = useMemo(() => {
    if (!previewImage) return { allImages: [], currentImageIndex: -1 };

    // 扁平化所有图片附件
    const images = messages.flatMap(m =>
      (m.attachments || [])
        .filter(att => att.mimeType.startsWith('image/') && att.url)
        .map(att => att.url!)
    );

    return {
      allImages: images,
      currentImageIndex: images.indexOf(previewImage)
    };
  }, [messages, previewImage]);

  // 下一张图片（循环）
  const handleNextImage = useCallback(() => {
    if (allImages.length <= 1) return;
    const nextIndex = currentImageIndex === allImages.length - 1 ? 0 : currentImageIndex + 1;
    setPreviewImage(allImages[nextIndex]);
  }, [allImages, currentImageIndex]);

  // 上一张图片（循环）
  const handlePrevImage = useCallback(() => {
    if (allImages.length <= 1) return;
    const prevIndex = currentImageIndex === 0 ? allImages.length - 1 : currentImageIndex - 1;
    setPreviewImage(allImages[prevIndex]);
  }, [allImages, currentImageIndex]);

  // 点击图片打开预览
  const handleImageClick = useCallback((url: string) => {
    setPreviewImage(url);
  }, []);

  return {
    previewImage,
    setPreviewImage,
    allImages,
    currentImageIndex,
    handleNextImage,
    handlePrevImage,
    handleImageClick
  };
};
