import { useState, useCallback, useRef, useEffect } from 'react';
import { AppMode } from '../types/types';
import { getAcceptedTypes, validateFilesForMode } from '../utils/fileValidation';

/**
 * 拖放 Hook 返回值
 */
export interface UseDragDropReturn {
  isDragging: boolean;
  isValidDrop: boolean;
  errorMessage: string;
  handleDragEnter: (e: React.DragEvent) => void;
  handleDragOver: (e: React.DragEvent) => void;
  handleDragLeave: (e: React.DragEvent) => void;
  handleDrop: (e: React.DragEvent) => void;
}

/**
 * 拖放 Hook 参数
 */
export interface UseDragDropOptions {
  mode: AppMode;
  currentAttachmentCount: number;
  onFilesDropped: (files: File[]) => void;
  disabled?: boolean;
}

/**
 * 拖放功能 Hook
 *
 * 处理文件拖放逻辑，包括：
 * - 拖放状态管理（使用 dragCounter 处理嵌套元素）
 * - 文件验证（类型、大小、模式限制）
 * - 视觉反馈（有效/无效状态）
 * - 错误消息显示
 */
export function useDragDrop({
  mode,
  currentAttachmentCount,
  onFilesDropped,
  disabled = false,
}: UseDragDropOptions): UseDragDropReturn {
  const [isDragging, setIsDragging] = useState(false);
  const [isValidDrop, setIsValidDrop] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  // 使用 dragCounter 处理嵌套元素的拖放事件
  const dragCounterRef = useRef(0);

  // 失败 drop 后用于延迟清除错误提示的定时器
  const errorTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const clearErrorTimer = useCallback(() => {
    if (errorTimerRef.current !== null) {
      clearTimeout(errorTimerRef.current);
      errorTimerRef.current = null;
    }
  }, []);

  // 卸载时清除挂起的定时器，避免对已卸载组件 setState
  useEffect(() => clearErrorTimer, [clearErrorTimer]);

  /**
   * 处理拖动进入事件
   */
  const handleDragEnter = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();

      if (disabled) return;

      // 新一轮拖动开始时，取消上次失败 drop 留下的延迟清理，避免拖动中被重置状态
      clearErrorTimer();

      dragCounterRef.current++;

      if (dragCounterRef.current === 1) {
        setIsDragging(true);
      }
    },
    [disabled, clearErrorTimer]
  );

  /**
   * 处理拖动悬停事件
   * 在这里进行文件验证，提供实时反馈
   */
  const handleDragOver = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();

      if (disabled) return;

      // dragover 阶段 drag data store 处于保护模式，getAsFile() 恒返回 null，
      // 只能读取 item.kind / item.type 元数据；大小等完整验证延后到 drop 阶段。
      const fileItems = Array.from(e.dataTransfer.items).filter((item) => item.kind === 'file');

      if (fileItems.length === 0) {
        setIsValidDrop(false);
        setErrorMessage('没有检测到文件');
        return;
      }

      // 扩图模式只允许一张图片（与 validateFilesForMode 的特殊限制保持一致）
      if (mode === 'image-outpainting' && currentAttachmentCount > 0) {
        setIsValidDrop(false);
        setErrorMessage('扩图模式只支持一张图片，请先移除现有图片');
        return;
      }

      const acceptedTypes = getAcceptedTypes(mode);
      const someTypeAcceptable =
        acceptedTypes.length > 0 &&
        fileItems.some((item) => {
          const itemType = item.type.toLowerCase();
          // 类型未知时无法判定，留待 drop 阶段做权威验证
          if (!itemType) return true;
          return acceptedTypes.some((accepted) => {
            const normalized = accepted.toLowerCase();
            // 扩展名规则需要文件名，拖动阶段不可见，留待 drop 验证
            if (normalized.startsWith('.')) return true;
            if (normalized.endsWith('/*')) {
              return itemType.startsWith(normalized.slice(0, -2));
            }
            return itemType === normalized;
          });
        });

      if (someTypeAcceptable) {
        setIsValidDrop(true);
        setErrorMessage('');
      } else {
        setIsValidDrop(false);
        setErrorMessage('文件验证失败');
      }
    },
    [disabled, mode, currentAttachmentCount]
  );

  /**
   * 处理拖动离开事件
   */
  const handleDragLeave = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();

      if (disabled) return;

      dragCounterRef.current--;

      if (dragCounterRef.current === 0) {
        setIsDragging(false);
        setIsValidDrop(false);
        setErrorMessage('');
      }
    },
    [disabled]
  );

  /**
   * 处理文件释放事件
   */
  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();

      if (disabled) return;

      // 重置状态
      dragCounterRef.current = 0;
      setIsDragging(false);
      setIsValidDrop(false);
      setErrorMessage('');

      // 提取文件
      const files = Array.from(e.dataTransfer.files);

      if (files.length === 0) return;

      // 验证文件
      const validation = validateFilesForMode(files, mode, currentAttachmentCount);

      if (validation.valid.length > 0) {
        onFilesDropped(validation.valid);
      }

      // 如果有错误，显示错误消息（通过短暂显示）
      if (validation.errors.length > 0) {
        setErrorMessage(validation.errors[0]);
        setIsDragging(true);
        setIsValidDrop(false);

        // 2秒后清除错误消息（可被新一轮拖动或卸载取消）
        clearErrorTimer();
        errorTimerRef.current = setTimeout(() => {
          errorTimerRef.current = null;
          setIsDragging(false);
          setErrorMessage('');
        }, 2000);
      }
    },
    [disabled, mode, currentAttachmentCount, onFilesDropped, clearErrorTimer]
  );

  return {
    isDragging,
    isValidDrop,
    errorMessage,
    handleDragEnter,
    handleDragOver,
    handleDragLeave,
    handleDrop,
  };
}
