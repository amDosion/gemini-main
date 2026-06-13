/**
 * useWorkflowResultMedia
 *
 * Extracts the result-derived memos and download/copy handlers that previously
 * lived inline in MultiAgentWorkflowEditorReactFlow.tsx:
 *
 * - renderedResultItems         (L1449-1580)
 * - sourceInputPreviewUrl       (L1582-1613)
 * - finalOutputImageUrls        (L1631-1646)
 * - finalOutputAudioUrls        (L1648-1663)
 * - finalOutputVideoUrls        (L1665-1680)
 * - renderableSourceInputPreviewUrl (L1682-1687)
 * - triggerWorkflowMediaDownload    (L1689-1704)
 * - handleBatchDownloadImages/Audio/Video (L1706-1728)
 * - handleCopyFinalResult       (L1437-1447)
 *
 * Behaviour is preserved 1:1 — every dedupe rule, every fallback, every
 * addLog call, and every JSON.stringify formatting matches the original.
 */

import { useCallback, useMemo } from 'react';
import type { Node } from 'reactflow';

import type { WorkflowNode, WorkflowNodeData } from '../types';
import { isNonResultWorkflowOutputNode } from '../workflowExport';
import { mergeUniqueStringList, normalizeStringList } from '../workflowGraphUtils';
import {
  extractAudioUrls,
  extractImageUrls,
  extractTextContent,
  extractThoughtContent,
  extractUrlContent,
  extractVideoUrls,
  isDirectlyRenderableAudioUrl,
  isDirectlyRenderableImageUrl,
  isDirectlyRenderableVideoUrl,
  isPlainObject,
  normalizeImageValue,
} from '../workflowResultUtils';
import { triggerBrowserDownload } from '../../../services/downloadService';

import type { LogLevel } from '../ExecutionLogPanel';

type AddLog = (
  nodeId: string,
  nodeName: string,
  level: LogLevel,
  message: string,
  timestamp?: number
) => void;

export interface RenderedResultItem {
  key: string;
  title: string;
  text: string;
  imageUrls: string[];
  audioUrls: string[];
  videoUrls: string[];
  urls: string[];
  thoughts: string[];
}

export interface UseWorkflowResultMediaArgs {
  finalResult: any;
  finalError: string | null;
  nodes: Node<WorkflowNodeData>[];
  workflowInputImageUrl: string;
  mergedResultPanelPreviewImageUrls: string[];
  resultPanelPreviewAudioUrls: string[];
  resultPanelPreviewVideoUrls: string[];
  executionId: string;
  addLog: AddLog;
}

export interface UseWorkflowResultMediaResult {
  renderedResultItems: RenderedResultItem[];
  sourceInputPreviewUrl: string | null;
  renderableSourceInputPreviewUrl: string | null;
  finalOutputImageUrls: string[];
  finalOutputAudioUrls: string[];
  finalOutputVideoUrls: string[];
  triggerWorkflowMediaDownload: (
    mediaKind: 'images' | 'audio' | 'video',
    successMessage: string
  ) => void;
  handleBatchDownloadImages: () => void;
  handleBatchDownloadAudio: () => void;
  handleBatchDownloadVideo: () => void;
  handleCopyFinalResult: () => Promise<void>;
}

export const useWorkflowResultMedia = ({
  finalResult,
  finalError,
  nodes,
  workflowInputImageUrl,
  mergedResultPanelPreviewImageUrls,
  resultPanelPreviewAudioUrls,
  resultPanelPreviewVideoUrls,
  executionId,
  addLog,
}: UseWorkflowResultMediaArgs): UseWorkflowResultMediaResult => {
  const handleCopyFinalResult = useCallback(async () => {
    const payload = finalError
      ? { error: finalError }
      : (finalResult ?? { message: '暂无可复制结果' });
    try {
      await navigator.clipboard.writeText(JSON.stringify(payload, null, 2));
      addLog('system', '系统', 'info', '已复制最终结果到剪贴板');
    } catch {
      addLog('system', '系统', 'warn', '复制失败，请检查浏览器权限');
    }
  }, [finalResult, finalError, addLog]);

  const renderedResultItems = useMemo<RenderedResultItem[]>(() => {
    if (finalResult == null) {
      return [];
    }

    const items: RenderedResultItem[] = [];
    const seenSignatures = new Set<string>();
    const seenImageUrls = new Set<string>();
    const seenAudioUrls = new Set<string>();
    const seenVideoUrls = new Set<string>();
    const seenUrls = new Set<string>();
    const nodeTypeById = new Map(
      (nodes as WorkflowNode[]).map((node) => [
        String(node?.id || '').trim(),
        String(node?.data?.type || node?.type || '')
          .trim()
          .toLowerCase(),
      ])
    );

    const pushItem = (key: string, title: string, payload: unknown, prefer = false) => {
      const rawText = extractTextContent(payload);
      const text = rawText.length > 2000 ? `${rawText.slice(0, 2000)}\n...(内容已截断)` : rawText;
      const imageUrls = extractImageUrls(payload);
      const audioUrls = extractAudioUrls(payload);
      const videoUrls = extractVideoUrls(payload);
      const thoughtItems = extractThoughtContent(payload);
      const renderedMediaUrls = new Set<string>();
      imageUrls.forEach((imageUrl) => {
        if (isDirectlyRenderableImageUrl(imageUrl)) {
          renderedMediaUrls.add(String(imageUrl).trim());
        }
      });
      audioUrls.forEach((audioUrl) => {
        if (isDirectlyRenderableAudioUrl(audioUrl)) {
          renderedMediaUrls.add(String(audioUrl).trim());
        }
      });
      videoUrls.forEach((videoUrl) => {
        if (isDirectlyRenderableVideoUrl(videoUrl)) {
          renderedMediaUrls.add(String(videoUrl).trim());
        }
      });
      const urls = Array.from(
        new Set(
          extractUrlContent(payload).filter((url) => !renderedMediaUrls.has(String(url).trim()))
        )
      );
      if (
        !text &&
        imageUrls.length === 0 &&
        audioUrls.length === 0 &&
        videoUrls.length === 0 &&
        thoughtItems.length === 0 &&
        urls.length === 0
      ) {
        return;
      }
      const hasUniqueImage = imageUrls.some((imageUrl) => !seenImageUrls.has(imageUrl));
      const hasUniqueAudio = audioUrls.some((audioUrl) => !seenAudioUrls.has(audioUrl));
      const hasUniqueVideo = videoUrls.some((videoUrl) => !seenVideoUrls.has(videoUrl));
      const hasUniqueUrl = urls.some((url) => !seenUrls.has(url));
      if (
        !prefer &&
        !hasUniqueImage &&
        !hasUniqueAudio &&
        !hasUniqueVideo &&
        !hasUniqueUrl &&
        thoughtItems.length === 0 &&
        text.length < 30
      ) {
        return;
      }
      const normalizedText = text.replace(/\s+/g, ' ').trim().slice(0, 400);
      const normalizedImages = imageUrls.map((imageUrl) => imageUrl.trim()).sort();
      const normalizedAudio = audioUrls.map((audioUrl) => audioUrl.trim()).sort();
      const normalizedVideo = videoUrls.map((videoUrl) => videoUrl.trim()).sort();
      const normalizedUrls = urls.map((url) => url.trim()).sort();
      const normalizedThoughts = thoughtItems
        .map((item) => item.replace(/\s+/g, ' ').trim().slice(0, 240))
        .sort();
      const signature = `${normalizedText}::${normalizedImages.join('|')}::${normalizedAudio.join('|')}::${normalizedVideo.join('|')}::${normalizedUrls.join('|')}::${normalizedThoughts.join('|')}`;
      if (seenSignatures.has(signature)) {
        return;
      }
      seenSignatures.add(signature);
      imageUrls.forEach((imageUrl) => seenImageUrls.add(imageUrl));
      audioUrls.forEach((audioUrl) => seenAudioUrls.add(audioUrl));
      videoUrls.forEach((videoUrl) => seenVideoUrls.add(videoUrl));
      urls.forEach((url) => seenUrls.add(url));
      items.push({
        key,
        title,
        text,
        imageUrls,
        audioUrls,
        videoUrls,
        urls,
        thoughts: thoughtItems,
      });
    };

    const finalOutput = isPlainObject(finalResult) ? finalResult.finalOutput : undefined;
    if (finalOutput !== undefined) {
      pushItem('final-output', '最终输出', finalOutput, true);
    } else {
      pushItem('final-result', '执行结果', finalResult, true);
    }

    const outputs = isPlainObject(finalResult)
      ? finalResult.outputs || finalResult.outputsMap || null
      : null;
    if (isPlainObject(outputs)) {
      Object.entries(outputs).forEach(([nodeId, output]) => {
        const nodeType = nodeTypeById.get(String(nodeId || '').trim()) || '';
        if (isNonResultWorkflowOutputNode(nodeId, nodeType)) {
          return;
        }
        const title =
          isPlainObject(output) && typeof output.agentName === 'string' && output.agentName
            ? `${output.agentName} (${nodeId})`
            : `节点 ${nodeId}`;
        pushItem(`node-${nodeId}`, title, output);
      });
    }

    return items;
  }, [finalResult, nodes]);

  const sourceInputPreviewUrl = useMemo(() => {
    const inputImageNode = (nodes as WorkflowNode[]).find((node) => {
      const nodeType = (node?.data?.type || node?.type || '').toLowerCase();
      return nodeType === 'input_image';
    });
    const fromInputNode = normalizeImageValue(
      mergeUniqueStringList(
        normalizeStringList(inputImageNode?.data?.startImageUrls),
        inputImageNode?.data?.startImageUrl
          ? [String(inputImageNode.data.startImageUrl).trim()]
          : []
      )[0] || ''
    );
    if (fromInputNode) {
      return fromInputNode;
    }

    const startNode = (nodes as WorkflowNode[]).find((node) => {
      const nodeType = (node?.data?.type || node?.type || '').toLowerCase();
      return nodeType === 'start';
    });
    const fromStartNode = normalizeImageValue(
      mergeUniqueStringList(
        normalizeStringList(startNode?.data?.startImageUrls),
        startNode?.data?.startImageUrl ? [String(startNode.data.startImageUrl).trim()] : []
      )[0] || ''
    );
    if (fromStartNode) {
      return fromStartNode;
    }
    return normalizeImageValue(workflowInputImageUrl);
  }, [nodes, workflowInputImageUrl]);

  const finalOutputImageUrls = useMemo(() => {
    const dedup = new Set<string>();
    renderedResultItems.forEach((item) => {
      item.imageUrls.forEach((imageUrl) => {
        if (imageUrl && isDirectlyRenderableImageUrl(imageUrl)) {
          dedup.add(imageUrl);
        }
      });
    });
    mergedResultPanelPreviewImageUrls.forEach((imageUrl) => {
      if (imageUrl && isDirectlyRenderableImageUrl(imageUrl)) {
        dedup.add(imageUrl);
      }
    });
    return Array.from(dedup);
  }, [mergedResultPanelPreviewImageUrls, renderedResultItems]);

  const finalOutputAudioUrls = useMemo(() => {
    const dedup = new Set<string>();
    renderedResultItems.forEach((item) => {
      item.audioUrls.forEach((audioUrl) => {
        if (audioUrl && isDirectlyRenderableAudioUrl(audioUrl)) {
          dedup.add(audioUrl);
        }
      });
    });
    resultPanelPreviewAudioUrls.forEach((audioUrl) => {
      if (audioUrl && isDirectlyRenderableAudioUrl(audioUrl)) {
        dedup.add(audioUrl);
      }
    });
    return Array.from(dedup);
  }, [renderedResultItems, resultPanelPreviewAudioUrls]);

  const finalOutputVideoUrls = useMemo(() => {
    const dedup = new Set<string>();
    renderedResultItems.forEach((item) => {
      item.videoUrls.forEach((videoUrl) => {
        if (videoUrl && isDirectlyRenderableVideoUrl(videoUrl)) {
          dedup.add(videoUrl);
        }
      });
    });
    resultPanelPreviewVideoUrls.forEach((videoUrl) => {
      if (videoUrl && isDirectlyRenderableVideoUrl(videoUrl)) {
        dedup.add(videoUrl);
      }
    });
    return Array.from(dedup);
  }, [renderedResultItems, resultPanelPreviewVideoUrls]);

  const renderableSourceInputPreviewUrl = useMemo(() => {
    if (!sourceInputPreviewUrl || !isDirectlyRenderableImageUrl(sourceInputPreviewUrl)) {
      return null;
    }
    return sourceInputPreviewUrl;
  }, [sourceInputPreviewUrl]);

  const triggerWorkflowMediaDownload = useCallback(
    (mediaKind: 'images' | 'audio' | 'video', successMessage: string) => {
      if (!executionId) {
        addLog('system', '系统', 'warn', '当前结果没有可用的执行记录，无法下载媒体');
        return;
      }
      triggerBrowserDownload({
        href: `/api/workflows/history/${encodeURIComponent(executionId)}/${mediaKind}/download`,
      });
      addLog('system', '系统', 'info', successMessage);
    },
    [addLog, executionId]
  );

  const handleBatchDownloadImages = useCallback(() => {
    if (finalOutputImageUrls.length === 0) {
      addLog('system', '系统', 'warn', '当前结果没有可下载图片');
      return;
    }
    triggerWorkflowMediaDownload('images', `已开始下载 ${finalOutputImageUrls.length} 张结果图片`);
  }, [addLog, finalOutputImageUrls.length, triggerWorkflowMediaDownload]);

  const handleBatchDownloadAudio = useCallback(() => {
    if (finalOutputAudioUrls.length === 0) {
      addLog('system', '系统', 'warn', '当前结果没有可下载音频');
      return;
    }
    triggerWorkflowMediaDownload('audio', `已开始下载 ${finalOutputAudioUrls.length} 条结果音频`);
  }, [addLog, finalOutputAudioUrls.length, triggerWorkflowMediaDownload]);

  const handleBatchDownloadVideo = useCallback(() => {
    if (finalOutputVideoUrls.length === 0) {
      addLog('system', '系统', 'warn', '当前结果没有可下载视频');
      return;
    }
    triggerWorkflowMediaDownload('video', `已开始下载 ${finalOutputVideoUrls.length} 条结果视频`);
  }, [addLog, finalOutputVideoUrls.length, triggerWorkflowMediaDownload]);

  return {
    renderedResultItems,
    sourceInputPreviewUrl,
    renderableSourceInputPreviewUrl,
    finalOutputImageUrls,
    finalOutputAudioUrls,
    finalOutputVideoUrls,
    triggerWorkflowMediaDownload,
    handleBatchDownloadImages,
    handleBatchDownloadAudio,
    handleBatchDownloadVideo,
    handleCopyFinalResult,
  };
};
