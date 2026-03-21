import { useState, useCallback, useRef } from 'react';
import { AppMode } from '../types/types';
import { validateFilesForMode } from '../utils/fileValidation';

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
  disabled = false
}: UseDragDropOptions): UseDragDropReturn {
  const [isDragging, setIsDragging] = useState(false);
  const [isValidDrop, setIsValidDrop] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  
  // 使用 dragCounter 处理嵌套元素的拖放事件
  const dragCounterRef = useRef(0);

  /**
   * 处理拖动进入事件
   */
  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    
    if (disabled) return;
    
    dragCounterRef.current++;
    
    if (dragCounterRef.current === 1) {
      setIsDragging(true);
    }
  }, [disabled]);

  /**
   * 处理拖动悬停事件
   * 在这里进行文件验证，提供实时反馈
   */
  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    
    if (disabled) return;
    
    // 提取拖放的文件
    const items = Array.from(e.dataTransfer.items);
    const files: File[] = [];
    
    items.forEach(item => {
      if (item.kind === 'file') {
        const file = item.getAsFile();
        if (file) files.push(file);
      }
    });
    
    if (files.length === 0) {
      setIsValidDrop(false);
      setErrorMessage('没有检测到文件');
      return;
    }
    
    // 验证文件
    const validation = validateFilesForMode(files, mode, currentAttachmentCount);
    
    if (validation.valid.length > 0) {
      setIsValidDrop(true);
      setErrorMessage('');
    } else {
      setIsValidDrop(false);
      setErrorMessage(validation.errors[0] || '文件验证失败');
    }
  }, [disabled, mode, currentAttachmentCount]);

  /**
   * 处理拖动离开事件
   */
  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    
    if (disabled) return;
    
    dragCounterRef.current--;
    
    if (dragCounterRef.current === 0) {
      setIsDragging(false);
      setIsValidDrop(false);
      setErrorMessage('');
    }
  }, [disabled]);

  /**
   * 处理文件释放事件
   */
  const handleDrop = useCallback((e: React.DragEvent) => {
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
      
      // 2秒后清除错误消息
      setTimeout(() => {
        setIsDragging(false);
        setErrorMessage('');
      }, 2000);
    }
  }, [disabled, mode, currentAttachmentCount, onFilesDropped]);

  return {
    isDragging,
    isValidDrop,
    errorMessage,
    handleDragEnter,
    handleDragOver,
    handleDragLeave,
    handleDrop
  };
}
