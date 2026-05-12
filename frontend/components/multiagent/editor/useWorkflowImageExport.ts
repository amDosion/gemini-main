/**
 * useWorkflowImageExport
 *
 * Extracts handleDownloadWorkflowImage (originally L411-621 of
 * MultiAgentWorkflowEditorReactFlow.tsx) into a dedicated hook that owns the
 * isExportingWorkflowImage UI flag and returns the bound callback.
 *
 * Behaviour is preserved 1:1 — every clone-time DOM tweak, fallback PNG/SVG
 * branch and addLog message remains identical to the original implementation.
 */

import { useCallback, useState } from 'react';
import type { ReactFlowInstance } from 'reactflow';
import { getNodesBounds } from 'reactflow';
import { toPng, toSvg } from 'html-to-image';

import {
  EXPORT_NODE_PADDING,
  EXPORT_MIN_WIDTH,
  EXPORT_MIN_HEIGHT,
  EXPORT_PNG_MAX_SIDE,
  EXPORT_PNG_MAX_PIXELS,
  EXPORT_PNG_TARGET_PIXELS,
  clampNumber,
  formatWorkflowExportError,
  ensureTempImageNoRedirect,
  waitForClonedImages,
} from '../workflowExport';

import type { LogLevel } from '../ExecutionLogPanel';

type AddLog = (
  nodeId: string,
  nodeName: string,
  level: LogLevel,
  message: string,
  timestamp?: number
) => void;

export interface UseWorkflowImageExportArgs {
  reactFlowInstance: ReactFlowInstance | null;
  reactFlowWrapperRef: React.RefObject<HTMLDivElement | null>;
  addLog: AddLog;
  setExecuteErrorBanner: (value: string | null) => void;
}

export interface UseWorkflowImageExportResult {
  handleDownloadWorkflowImage: () => Promise<void>;
  isExportingWorkflowImage: boolean;
}

export const useWorkflowImageExport = ({
  reactFlowInstance,
  reactFlowWrapperRef,
  addLog,
  setExecuteErrorBanner,
}: UseWorkflowImageExportArgs): UseWorkflowImageExportResult => {
  const [isExportingWorkflowImage, setIsExportingWorkflowImage] = useState(false);

  const handleDownloadWorkflowImage = useCallback(async () => {
    if (isExportingWorkflowImage) {
      return;
    }

    if (!reactFlowInstance) {
      addLog('system', '系统', 'warn', '画布尚未初始化，暂时无法下载');
      setExecuteErrorBanner('下载失败：画布尚未初始化，请稍后重试。');
      return;
    }

    const workflowNodes = reactFlowInstance.getNodes();
    if (!Array.isArray(workflowNodes) || workflowNodes.length === 0) {
      addLog('system', '系统', 'warn', '当前画布没有节点可下载');
      setExecuteErrorBanner('下载失败：当前画布没有可导出的节点。');
      return;
    }

    const flowElement = reactFlowWrapperRef.current?.querySelector(
      '.react-flow'
    ) as HTMLElement | null;
    if (!flowElement) {
      addLog('system', '系统', 'warn', '未找到 React Flow 根容器，下载失败');
      setExecuteErrorBanner('下载失败：未找到画布容器。');
      return;
    }

    const nodeBounds = getNodesBounds(workflowNodes);
    const expandedBounds = {
      x: nodeBounds.x - EXPORT_NODE_PADDING,
      y: nodeBounds.y - EXPORT_NODE_PADDING,
      width: nodeBounds.width + EXPORT_NODE_PADDING * 2,
      height: nodeBounds.height + EXPORT_NODE_PADDING * 2,
    };

    const imageWidth = Math.max(Math.ceil(expandedBounds.width), EXPORT_MIN_WIDTH);
    const imageHeight = Math.max(Math.ceil(expandedBounds.height), EXPORT_MIN_HEIGHT);
    const exportArea = imageWidth * imageHeight;
    const shouldExportAsSvg =
      imageWidth > EXPORT_PNG_MAX_SIDE ||
      imageHeight > EXPORT_PNG_MAX_SIDE ||
      exportArea > EXPORT_PNG_MAX_PIXELS;
    const exportPixelRatio = clampNumber(
      Math.sqrt(EXPORT_PNG_TARGET_PIXELS / Math.max(1, exportArea)),
      1.35,
      3.5
    );
    const offscreenWrapper = document.createElement('div');
    offscreenWrapper.style.position = 'fixed';
    offscreenWrapper.style.left = '-99999px';
    offscreenWrapper.style.top = '-99999px';
    offscreenWrapper.style.width = `${imageWidth}px`;
    offscreenWrapper.style.height = `${imageHeight}px`;
    offscreenWrapper.style.pointerEvents = 'none';
    offscreenWrapper.style.opacity = '0';
    offscreenWrapper.style.zIndex = '-1';

    const flowClone = flowElement.cloneNode(true) as HTMLElement;
    flowClone.style.width = `${imageWidth}px`;
    flowClone.style.height = `${imageHeight}px`;
    flowClone.style.background = '#0f172a';
    flowClone.style.overflow = 'hidden';

    flowClone
      .querySelectorAll(
        '.react-flow__controls, .react-flow__minimap, .react-flow__attribution, .react-flow__panel'
      )
      .forEach((element) => element.remove());

    const viewportClone = flowClone.querySelector('.react-flow__viewport') as HTMLElement | null;
    if (!viewportClone) {
      addLog('system', '系统', 'warn', '未找到导出视口，下载失败');
      setExecuteErrorBanner('下载失败：未找到导出视口。');
      return;
    }
    viewportClone.style.transform = `translate(${-expandedBounds.x}px, ${-expandedBounds.y}px) scale(1)`;
    viewportClone.style.transformOrigin = '0 0';

    const clonedImages = Array.from(flowClone.querySelectorAll('img[src]')) as HTMLImageElement[];
    clonedImages.forEach((img) => {
      const currentSrc = img.getAttribute('src') || '';
      const nextSrc = ensureTempImageNoRedirect(currentSrc);
      if (nextSrc !== currentSrc) {
        img.setAttribute('src', nextSrc);
      }
      img.setAttribute('crossorigin', 'anonymous');
      img.removeAttribute('srcset');
    });
    offscreenWrapper.appendChild(flowClone);

    setExecuteErrorBanner(null);
    setIsExportingWorkflowImage(true);

    try {
      document.body.appendChild(offscreenWrapper);
      await waitForClonedImages(flowClone);

      let dataUrl: string;
      let fileExtension: 'png' | 'svg' = shouldExportAsSvg ? 'svg' : 'png';
      try {
        if (shouldExportAsSvg) {
          dataUrl = await toSvg(flowClone, {
            backgroundColor: '#0f172a',
            cacheBust: true,
            width: imageWidth,
            height: imageHeight,
            style: {
              width: `${imageWidth}px`,
              height: `${imageHeight}px`,
            },
          });
          setExecuteErrorBanner('流程较大，已自动导出为 SVG 无损格式以保证清晰度。');
        } else {
          dataUrl = await toPng(flowClone, {
            backgroundColor: '#0f172a',
            cacheBust: true,
            pixelRatio: exportPixelRatio,
            width: imageWidth,
            height: imageHeight,
            style: {
              width: `${imageWidth}px`,
              height: `${imageHeight}px`,
            },
          });
        }
      } catch {
        if (shouldExportAsSvg) {
          dataUrl = await toSvg(flowClone, {
            backgroundColor: '#0f172a',
            cacheBust: true,
            width: imageWidth,
            height: imageHeight,
            style: {
              width: `${imageWidth}px`,
              height: `${imageHeight}px`,
            },
            filter: (domNode: HTMLElement) => {
              if (domNode instanceof HTMLImageElement) {
                const source = String(domNode.getAttribute('src') || domNode.src || '').trim();
                if (!source) return false;
                if (source.startsWith('data:') || source.startsWith('blob:')) return true;
                if (source.startsWith('/') || source.startsWith(window.location.origin))
                  return true;
                return false;
              }
              return true;
            },
          });
          fileExtension = 'svg';
        } else {
          dataUrl = await toPng(flowClone, {
            backgroundColor: '#0f172a',
            cacheBust: true,
            pixelRatio: exportPixelRatio,
            width: imageWidth,
            height: imageHeight,
            style: {
              width: `${imageWidth}px`,
              height: `${imageHeight}px`,
            },
            filter: (domNode: HTMLElement) => {
              if (domNode instanceof HTMLImageElement) {
                const source = String(domNode.getAttribute('src') || domNode.src || '').trim();
                if (!source) return false;
                if (source.startsWith('data:') || source.startsWith('blob:')) return true;
                if (source.startsWith('/') || source.startsWith(window.location.origin))
                  return true;
                return false;
              }
              return true;
            },
          });
          fileExtension = 'png';
        }
        setExecuteErrorBanner('已导出图片，但已自动跳过无法跨域加载的图片资源。');
      }

      const timestamp = `${Date.now()}`;
      const anchor = document.createElement('a');
      anchor.href = dataUrl;
      anchor.download = `workflow-${timestamp}.${fileExtension}`;
      document.body.appendChild(anchor);
      anchor.click();
      document.body.removeChild(anchor);
      addLog(
        'system',
        '系统',
        'info',
        `已下载工作流画布图片（${fileExtension.toUpperCase()}，${imageWidth}×${imageHeight}${fileExtension === 'png' ? `，倍率 ${exportPixelRatio.toFixed(2)}` : ''}）`
      );
    } catch (error) {
      const rawMessage = formatWorkflowExportError(error);
      const lower = rawMessage.toLowerCase();
      const message =
        lower.includes('tainted') ||
        lower.includes('cross') ||
        lower.includes('cors') ||
        lower.includes('security') ||
        lower.includes('failed to fetch')
          ? '下载失败：检测到跨域图片资源无法导出，请确认图片可经 /api/temp-images/*?no_redirect=1 访问。'
          : `下载失败：${rawMessage}`;
      addLog('system', '系统', 'error', `下载工作流图片失败: ${rawMessage}`);
      setExecuteErrorBanner(message);
    } finally {
      if (offscreenWrapper.parentNode) {
        offscreenWrapper.parentNode.removeChild(offscreenWrapper);
      }
      setIsExportingWorkflowImage(false);
    }
  }, [
    addLog,
    isExportingWorkflowImage,
    reactFlowInstance,
    reactFlowWrapperRef,
    setExecuteErrorBanner,
  ]);

  return {
    handleDownloadWorkflowImage,
    isExportingWorkflowImage,
  };
};
