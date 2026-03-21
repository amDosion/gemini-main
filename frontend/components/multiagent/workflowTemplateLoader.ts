import type { Dispatch, SetStateAction } from 'react';
import type { Edge, Node } from 'reactflow';
import { fetchWorkflowPreviewImages } from '../../services/workflowHistoryService';
import type { WorkflowNodeData } from './types';
import {
  buildPresetPromptValue,
  buildWorkflowStructureFingerprint,
  normalizeLoadedNode,
  normalizeTemplateSampleInput,
  resolveTemplateInputPlaceholder,
} from './workflowEditorUtils';
import { hydrateNodePortLayoutsFromEdges } from './workflowPorts';
import {
  hasUsableImageInput,
  isPlainObject,
  mergePreviewImagesIntoResult,
  mergePreviewMediaIntoResult,
} from './workflowResultUtils';
import { mergeRuntimeHints } from '../views/multiagent/runtimeHints';

interface ActiveTemplateMeta {
  templateId: string;
  templateName?: string;
  id?: string;
  name?: string;
  description?: string;
  category?: string;
  tags?: string[];
  isEditable?: boolean;
  isLocked?: boolean;
}

interface LoadTemplateIntoEditorOptions {
  template: any;
  setWorkflowPrompt: Dispatch<SetStateAction<string>>;
  setWorkflowInputImageUrl: Dispatch<SetStateAction<string>>;
  setWorkflowInputFileUrl: Dispatch<SetStateAction<string>>;
  setNodes: Dispatch<SetStateAction<Node<WorkflowNodeData>[]>>;
  setEdges: Dispatch<SetStateAction<Edge[]>>;
  setActiveTemplateMeta: Dispatch<SetStateAction<ActiveTemplateMeta | null>>;
  setActiveTemplateFingerprint: Dispatch<SetStateAction<string | null>>;
  setFinalResult: Dispatch<SetStateAction<any>>;
  setFinalError: Dispatch<SetStateAction<string | null>>;
  setFinalCompletedAt: Dispatch<SetStateAction<number | null>>;
  setFinalRuntime: Dispatch<SetStateAction<string>>;
  setFinalRuntimeHints: Dispatch<SetStateAction<string[]>>;
  setShowTemplateSelector: Dispatch<SetStateAction<boolean>>;
  setPendingFitToken: (token: string) => void;
  addLog: (id: string, name: string, level: 'info' | 'warn' | 'error', message: string, timestamp?: number) => void;
  hydrateAgentBindingsFromRegistry: (
    inputNodes: Node<WorkflowNodeData>[]
  ) => Promise<Node<WorkflowNodeData>[]>;
}

export const loadTemplateIntoEditor = async ({
  template,
  setWorkflowPrompt,
  setWorkflowInputImageUrl,
  setWorkflowInputFileUrl,
  setNodes,
  setEdges,
  setActiveTemplateMeta,
  setActiveTemplateFingerprint,
  setFinalResult,
  setFinalError,
  setFinalCompletedAt,
  setFinalRuntime,
  setFinalRuntimeHints,
  setShowTemplateSelector,
  setPendingFitToken,
  addLog,
  hydrateAgentBindingsFromRegistry,
}: LoadTemplateIntoEditorOptions): Promise<void> => {
  const templateSampleResult = template?.sampleResult ?? null;
  const rawSampleSummary = template?.sampleResultSummary;
  const templateSampleSummary = isPlainObject(rawSampleSummary) ? rawSampleSummary : null;
  const templateSampleInput = normalizeTemplateSampleInput(template?.sampleInput);
  const templateSampleHasResult = Boolean(
    (templateSampleSummary && templateSampleSummary.hasResult)
    || templateSampleResult !== null
  );
  const templateSampleRuntime = String(templateSampleSummary?.primaryRuntime || '').trim();
  const templateSampleRuntimeHints = mergeRuntimeHints(
    [],
    Array.isArray(templateSampleSummary?.runtimeHints) ? templateSampleSummary.runtimeHints : [],
  );
  const templateSamplePreviewImageUrls = Array.isArray(templateSampleSummary?.imageUrls)
    ? templateSampleSummary.imageUrls
      .map((item: any) => String(item || '').trim())
      .filter((item: string) => item.length > 0)
    : [];
  const templateSamplePreviewAudioUrls = Array.isArray(templateSampleSummary?.audioUrls)
    ? templateSampleSummary.audioUrls
      .map((item: any) => String(item || '').trim())
      .filter((item: string) => item.length > 0)
    : [];
  const templateSamplePreviewVideoUrls = Array.isArray(templateSampleSummary?.videoUrls)
    ? templateSampleSummary.videoUrls
      .map((item: any) => String(item || '').trim())
      .filter((item: string) => item.length > 0)
    : [];
  const templateSampleExecutionId = String(template?.sampleExecutionId || '').trim();
  const templateSampleUpdatedAt = Number(template?.sampleResultUpdatedAt || 0) || null;

  const requiresImageTemplate = Boolean(template?.requiresImage);
  let templateHasUsableImage = false;
  const templateNodes = Array.isArray(template?.config?.nodes)
    ? template.config.nodes.map((node: any, index: number) => normalizeLoadedNode(node, index))
    : [];
  const templateNodeIdSet = new Set(templateNodes.map((node: any) => node.id));
  const templateEdges = Array.isArray(template?.config?.edges)
    ? template.config.edges
      .map((edge: any, index: number) => ({
        ...edge,
        id: String(edge?.id || `edge-template-${index}-${Date.now()}`),
      }))
      .filter((edge: any) => templateNodeIdSet.has(String(edge?.source || '')) && templateNodeIdSet.has(String(edge?.target || '')))
    : [];
  const templateNodesWithPortLayout = hydrateNodePortLayoutsFromEdges(templateNodes as Node<WorkflowNodeData>[], templateEdges as Edge[]);

  const loadedPrompt = buildPresetPromptValue(template);
  let parsedTask = '';
  let parsedImageUrl = '';
  let parsedImageUrls: string[] = [];
  let parsedVideoUrl = '';
  let parsedVideoUrls: string[] = [];
  let parsedAudioUrl = '';
  let parsedAudioUrls: string[] = [];
  let parsedPrompts: string[] = [];
  let parsedFileUrl = '';
  let parsedFileUrls: string[] = [];
  if (loadedPrompt) {
    setWorkflowPrompt(loadedPrompt);
    try {
      const parsed = JSON.parse(loadedPrompt);
      if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
        parsedTask = String(parsed.task || parsed.prompt || parsed.text || '');
        if (typeof parsed.imageUrl === 'string') {
          if (hasUsableImageInput(parsed.imageUrl)) {
            parsedImageUrl = parsed.imageUrl.trim();
            setWorkflowInputImageUrl(parsedImageUrl);
            templateHasUsableImage = true;
          } else {
            setWorkflowInputImageUrl('');
          }
        }
        if (Array.isArray(parsed.imageUrls)) {
          parsedImageUrls = parsed.imageUrls
            .map((item: any) => String(item || '').trim())
            .filter(Boolean);
          if (!parsedImageUrl && parsedImageUrls.length > 0) {
            parsedImageUrl = parsedImageUrls[0];
            setWorkflowInputImageUrl(parsedImageUrl);
            templateHasUsableImage = true;
          }
        }
        if (typeof parsed.videoUrl === 'string') {
          parsedVideoUrl = parsed.videoUrl.trim();
        }
        if (typeof (parsed as any).video_url === 'string' && !parsedVideoUrl) {
          parsedVideoUrl = String((parsed as any).video_url || '').trim();
        }
        if (Array.isArray(parsed.videoUrls)) {
          parsedVideoUrls = parsed.videoUrls
            .map((item: any) => String(item || '').trim())
            .filter(Boolean);
        }
        if (Array.isArray((parsed as any).video_urls)) {
          parsedVideoUrls = Array.from(new Set([
            ...parsedVideoUrls,
            ...(parsed as any).video_urls
              .map((item: any) => String(item || '').trim())
              .filter(Boolean),
          ]));
        }
        if (!parsedVideoUrl && parsedVideoUrls.length > 0) {
          parsedVideoUrl = parsedVideoUrls[0];
        }
        if (typeof parsed.audioUrl === 'string') {
          parsedAudioUrl = parsed.audioUrl.trim();
        }
        if (typeof (parsed as any).audio_url === 'string' && !parsedAudioUrl) {
          parsedAudioUrl = String((parsed as any).audio_url || '').trim();
        }
        if (Array.isArray(parsed.audioUrls)) {
          parsedAudioUrls = parsed.audioUrls
            .map((item: any) => String(item || '').trim())
            .filter(Boolean);
        }
        if (Array.isArray((parsed as any).audio_urls)) {
          parsedAudioUrls = Array.from(new Set([
            ...parsedAudioUrls,
            ...(parsed as any).audio_urls
              .map((item: any) => String(item || '').trim())
              .filter(Boolean),
          ]));
        }
        if (!parsedAudioUrl && parsedAudioUrls.length > 0) {
          parsedAudioUrl = parsedAudioUrls[0];
        }
        if (Array.isArray(parsed.prompts)) {
          parsedPrompts = parsed.prompts
            .map((item: any) => String(item || '').trim())
            .filter(Boolean);
        }
        if (typeof parsed.fileUrl === 'string') {
          parsedFileUrl = parsed.fileUrl.trim();
        }
        if (Array.isArray(parsed.fileUrls)) {
          parsedFileUrls = parsed.fileUrls
            .map((item: any) => String(item || '').trim())
            .filter(Boolean);
        }
        if (Array.isArray((parsed as any).file_urls)) {
          parsedFileUrls = Array.from(new Set([
            ...parsedFileUrls,
            ...(parsed as any).file_urls
              .map((item: any) => String(item || '').trim())
              .filter(Boolean),
          ]));
        }
        if (!parsedFileUrl && parsedFileUrls.length > 0) {
          parsedFileUrl = parsedFileUrls[0];
        }
      }
    } catch {
      parsedTask = loadedPrompt;
    }
  }
  if (!loadedPrompt && templateSampleInput.task) {
    setWorkflowPrompt(templateSampleInput.task);
  }
  if (!parsedImageUrl && templateSampleInput.imageUrl) {
    parsedImageUrl = templateSampleInput.imageUrl;
    setWorkflowInputImageUrl(parsedImageUrl);
    templateHasUsableImage = true;
  }
  if (!parsedFileUrl && templateSampleInput.fileUrl) {
    parsedFileUrl = templateSampleInput.fileUrl;
  }
  if (!parsedTask && templateSampleInput.task) {
    parsedTask = templateSampleInput.task;
  }
  if (parsedImageUrls.length === 0 && templateSampleInput.imageUrls.length > 0) {
    parsedImageUrls = [...templateSampleInput.imageUrls];
  }
  if (!parsedVideoUrl && templateSampleInput.videoUrl) {
    parsedVideoUrl = templateSampleInput.videoUrl;
  }
  if (parsedVideoUrls.length === 0 && templateSampleInput.videoUrls.length > 0) {
    parsedVideoUrls = [...templateSampleInput.videoUrls];
  }
  if (!parsedVideoUrl && parsedVideoUrls.length > 0) {
    parsedVideoUrl = parsedVideoUrls[0];
  }
  if (!parsedAudioUrl && templateSampleInput.audioUrl) {
    parsedAudioUrl = templateSampleInput.audioUrl;
  }
  if (parsedAudioUrls.length === 0 && templateSampleInput.audioUrls.length > 0) {
    parsedAudioUrls = [...templateSampleInput.audioUrls];
  }
  if (!parsedAudioUrl && parsedAudioUrls.length > 0) {
    parsedAudioUrl = parsedAudioUrls[0];
  }
  if (parsedFileUrls.length === 0 && templateSampleInput.fileUrls.length > 0) {
    parsedFileUrls = [...templateSampleInput.fileUrls];
  }
  if (!parsedFileUrl && parsedFileUrls.length > 0) {
    parsedFileUrl = parsedFileUrls[0];
  }
  setWorkflowInputFileUrl(parsedFileUrl || '');
  if (parsedPrompts.length === 0 && templateSampleInput.prompts.length > 0) {
    parsedPrompts = [...templateSampleInput.prompts];
  }

  let imageAutoIndex = 0;
  let promptAutoIndex = 0;
  let videoAutoIndex = 0;
  let audioAutoIndex = 0;
  const hydratedTemplateNodes = templateNodesWithPortLayout.map((node) => {
    const nodeType = (node?.data?.type || node?.type || '').toLowerCase();
    if (nodeType === 'end') {
      const nextData: Record<string, any> = { ...node.data };
      if (templateSampleHasResult) {
        nextData.result = templateSampleResult;
        nextData.status = 'completed';
        nextData.progress = 100;
        nextData.error = undefined;
        if (templateSampleRuntime) {
          nextData.runtime = templateSampleRuntime;
        }
      } else {
        nextData.result = undefined;
        nextData.status = 'pending';
        nextData.progress = 0;
        nextData.error = undefined;
        nextData.runtime = undefined;
      }
      return {
        ...node,
        data: nextData,
      };
    }
    if (!['start', 'input_text', 'input_image', 'input_video', 'input_audio', 'input_file'].includes(nodeType)) {
      return node;
    }
    const nextData: Record<string, any> = { ...node.data };
    const buildSampleInputContext = (overrides: Partial<typeof templateSampleInput> = {}) => ({
      ...templateSampleInput,
      task: parsedTask || templateSampleInput.task || loadedPrompt || '',
      imageUrl: parsedImageUrl || templateSampleInput.imageUrl,
      imageUrls: parsedImageUrls.length > 0 ? parsedImageUrls : templateSampleInput.imageUrls,
      videoUrl: parsedVideoUrl || templateSampleInput.videoUrl,
      videoUrls: parsedVideoUrls.length > 0 ? parsedVideoUrls : templateSampleInput.videoUrls,
      audioUrl: parsedAudioUrl || templateSampleInput.audioUrl,
      audioUrls: parsedAudioUrls.length > 0 ? parsedAudioUrls : templateSampleInput.audioUrls,
      prompts: parsedPrompts.length > 0 ? parsedPrompts : templateSampleInput.prompts,
      fileUrl: parsedFileUrl || templateSampleInput.fileUrl,
      fileUrls: parsedFileUrls.length > 0 ? parsedFileUrls : templateSampleInput.fileUrls,
      ...overrides,
    });
    if (nodeType === 'start' || nodeType === 'input_text') {
      const promptFallback = parsedPrompts[promptAutoIndex] || parsedTask || loadedPrompt || templateSampleInput.task || '';
      const resolvedTask = resolveTemplateInputPlaceholder(
        node.data?.startTask,
        buildSampleInputContext(),
        promptFallback,
      );
      nextData.startTask = String(resolvedTask || promptFallback || '').trim();
      if (nodeType === 'input_text' && (nextData.startTask || promptFallback)) {
        promptAutoIndex += 1;
      }
    }
    if (nodeType === 'start' || nodeType === 'input_image') {
      const imagePool = parsedImageUrls.length > 0 ? parsedImageUrls : templateSampleInput.imageUrls;
      const imageFallback = imagePool[imageAutoIndex] || parsedImageUrl || templateSampleInput.imageUrl || '';
      const resolvedImage = resolveTemplateInputPlaceholder(
        node.data?.startImageUrl,
        buildSampleInputContext({ imageUrls: imagePool }),
        imageFallback,
      );
      const rawNodeImageUrls = Array.isArray(node.data?.startImageUrls) ? node.data.startImageUrls : [];
      const resolvedNodeImageUrls = rawNodeImageUrls
        .map((item: any, index: number) => resolveTemplateInputPlaceholder(
          item,
          buildSampleInputContext({ imageUrls: imagePool }),
          imagePool[index] || imageFallback,
        ))
        .map((item: any) => String(item || '').trim())
        .filter(Boolean);
      const normalizedImage = String(resolvedImage || imageFallback || '').trim();
      const nextImageUrls = Array.from(new Set([
        ...resolvedNodeImageUrls,
        normalizedImage,
        ...(nodeType === 'start' && resolvedNodeImageUrls.length === 0 ? imagePool : []),
      ].filter(Boolean)));
      nextData.startImageUrl = nextImageUrls[0] || '';
      nextData.startImageUrls = nextImageUrls;
      if (nodeType === 'input_image' && nextData.startImageUrl) {
        imageAutoIndex += 1;
        templateHasUsableImage = templateHasUsableImage || hasUsableImageInput(nextData.startImageUrl);
      }
    }
    if (nodeType === 'start' || nodeType === 'input_video') {
      const videoPool = parsedVideoUrls.length > 0 ? parsedVideoUrls : templateSampleInput.videoUrls;
      const videoFallback = videoPool[videoAutoIndex] || parsedVideoUrl || templateSampleInput.videoUrl || '';
      const resolvedVideo = resolveTemplateInputPlaceholder(
        node.data?.startVideoUrl,
        buildSampleInputContext({ videoUrls: videoPool }),
        videoFallback,
      );
      const rawNodeVideoUrls = Array.isArray(node.data?.startVideoUrls) ? node.data.startVideoUrls : [];
      const resolvedNodeVideoUrls = rawNodeVideoUrls
        .map((item: any, index: number) => resolveTemplateInputPlaceholder(
          item,
          buildSampleInputContext({ videoUrls: videoPool }),
          videoPool[index] || videoFallback,
        ))
        .map((item: any) => String(item || '').trim())
        .filter(Boolean);
      const normalizedVideo = String(resolvedVideo || videoFallback || '').trim();
      const nextVideoUrls = Array.from(new Set([
        ...resolvedNodeVideoUrls,
        normalizedVideo,
        ...(nodeType === 'start' && resolvedNodeVideoUrls.length === 0 ? videoPool : []),
      ].filter(Boolean)));
      nextData.startVideoUrl = nextVideoUrls[0] || '';
      nextData.startVideoUrls = nextVideoUrls;
      if (nodeType === 'input_video' && nextData.startVideoUrl) {
        videoAutoIndex += 1;
      }
    }
    if (nodeType === 'start' || nodeType === 'input_audio') {
      const audioPool = parsedAudioUrls.length > 0 ? parsedAudioUrls : templateSampleInput.audioUrls;
      const audioFallback = audioPool[audioAutoIndex] || parsedAudioUrl || templateSampleInput.audioUrl || '';
      const resolvedAudio = resolveTemplateInputPlaceholder(
        node.data?.startAudioUrl,
        buildSampleInputContext({ audioUrls: audioPool }),
        audioFallback,
      );
      const rawNodeAudioUrls = Array.isArray(node.data?.startAudioUrls) ? node.data.startAudioUrls : [];
      const resolvedNodeAudioUrls = rawNodeAudioUrls
        .map((item: any, index: number) => resolveTemplateInputPlaceholder(
          item,
          buildSampleInputContext({ audioUrls: audioPool }),
          audioPool[index] || audioFallback,
        ))
        .map((item: any) => String(item || '').trim())
        .filter(Boolean);
      const normalizedAudio = String(resolvedAudio || audioFallback || '').trim();
      const nextAudioUrls = Array.from(new Set([
        ...resolvedNodeAudioUrls,
        normalizedAudio,
        ...(nodeType === 'start' && resolvedNodeAudioUrls.length === 0 ? audioPool : []),
      ].filter(Boolean)));
      nextData.startAudioUrl = nextAudioUrls[0] || '';
      nextData.startAudioUrls = nextAudioUrls;
      if (nodeType === 'input_audio' && nextData.startAudioUrl) {
        audioAutoIndex += 1;
      }
    }
    if (nodeType === 'start' || nodeType === 'input_file') {
      const filePool = parsedFileUrls.length > 0 ? parsedFileUrls : templateSampleInput.fileUrls;
      const fileFallback = parsedFileUrl || templateSampleInput.fileUrl || filePool[0] || '';
      const resolvedFile = resolveTemplateInputPlaceholder(
        node.data?.startFileUrl,
        buildSampleInputContext({ fileUrls: filePool }),
        fileFallback,
      );
      const rawNodeFileUrls = Array.isArray(node.data?.startFileUrls) ? node.data.startFileUrls : [];
      const resolvedNodeFileUrls = rawNodeFileUrls
        .map((item: any, index: number) => resolveTemplateInputPlaceholder(
          item,
          buildSampleInputContext({ fileUrls: filePool }),
          filePool[index] || fileFallback,
        ))
        .map((item: any) => String(item || '').trim())
        .filter(Boolean);
      const normalizedFile = String(resolvedFile || fileFallback || '').trim();
      const nextFileUrls = Array.from(new Set([
        ...resolvedNodeFileUrls,
        normalizedFile,
        ...(nodeType === 'start' && resolvedNodeFileUrls.length === 0 ? filePool : []),
      ].filter(Boolean)));
      nextData.startFileUrl = nextFileUrls[0] || '';
      nextData.startFileUrls = nextFileUrls;
    }
    return {
      ...node,
      data: nextData,
    };
  });

  let templatePreviewImageUrls = [...templateSamplePreviewImageUrls];
  if (templateSampleHasResult && templateSampleExecutionId) {
    try {
      const fetchedPreviewImages = await fetchWorkflowPreviewImages(templateSampleExecutionId);
      if (fetchedPreviewImages.length > 0) {
        templatePreviewImageUrls = Array.from(new Set([
          ...templatePreviewImageUrls,
          ...fetchedPreviewImages.map((item) => String(item || '').trim()).filter(Boolean),
        ]));
      }
    } catch (error) {
      addLog('system', '系统', 'warn', `模板样例结果预览图加载失败: ${error}`);
    }
  }

  let mergedTemplateSampleResult = templateSampleHasResult
    ? mergePreviewImagesIntoResult(templateSampleResult, templatePreviewImageUrls)
    : null;
  if (templateSampleHasResult && templateSamplePreviewAudioUrls.length > 0) {
    mergedTemplateSampleResult = mergePreviewMediaIntoResult(
      mergedTemplateSampleResult,
      'audio',
      templateSamplePreviewAudioUrls,
    );
  }
  if (templateSampleHasResult && templateSamplePreviewVideoUrls.length > 0) {
    mergedTemplateSampleResult = mergePreviewMediaIntoResult(
      mergedTemplateSampleResult,
      'video',
      templateSamplePreviewVideoUrls,
    );
  }
  if (templateSampleHasResult && templateSampleSummary) {
    const mergedMetadata = {
      continuationStrategy: String(
        templateSampleSummary?.continuationStrategy || templateSampleSummary?.continuation_strategy || ''
      ).trim() || undefined,
      videoExtensionCount: Number(
        (templateSampleSummary?.videoExtensionCount ?? templateSampleSummary?.video_extension_count) || 0
      ) || undefined,
      videoExtensionApplied: Number(
        (templateSampleSummary?.videoExtensionApplied ?? templateSampleSummary?.video_extension_applied) || 0
      ) || undefined,
      totalDurationSeconds: Number(
        (templateSampleSummary?.totalDurationSeconds ?? templateSampleSummary?.total_duration_seconds) || 0
      ) || undefined,
      continuedFromVideo: Boolean(
        templateSampleSummary?.continuedFromVideo ?? templateSampleSummary?.continued_from_video ?? false
      ),
      subtitleMode: String(
        templateSampleSummary?.subtitleMode || templateSampleSummary?.subtitle_mode || ''
      ).trim() || undefined,
      subtitleFileCount: Number(
        (templateSampleSummary?.subtitleFileCount ?? templateSampleSummary?.subtitle_file_count) || 0
      ) || undefined,
    };
    mergedTemplateSampleResult = isPlainObject(mergedTemplateSampleResult)
      ? { ...mergedTemplateSampleResult, ...mergedMetadata }
      : mergedMetadata;
  }

  const nodesWithAgentBinding = await hydrateAgentBindingsFromRegistry(hydratedTemplateNodes as Node<WorkflowNodeData>[]);
  const nodesWithSampleResult: Node<WorkflowNodeData>[] = templateSampleHasResult
    ? (nodesWithAgentBinding as Node<WorkflowNodeData>[]).map((node) => {
      const nodeType = String(node?.data?.type || node?.type || '').toLowerCase();
      if (nodeType !== 'end') {
        return node;
      }
      return {
        ...node,
        data: {
          ...node.data,
          result: mergedTemplateSampleResult,
          status: 'completed' as const,
          progress: 100,
          error: undefined,
          runtime: templateSampleRuntime || node.data?.runtime,
        },
      };
    }) as Node<WorkflowNodeData>[]
    : (nodesWithAgentBinding as Node<WorkflowNodeData>[]);

  setNodes(nodesWithSampleResult);
  setEdges(templateEdges);
  const templateId = String(template?.id || '').trim();
  setActiveTemplateMeta(templateId ? {
    templateId,
    templateName: String(template?.name || '').trim(),
    id: templateId,
    name: String(template?.name || '').trim(),
    description: String(template?.description || '').trim(),
    category: String(template?.category || '').trim(),
    tags: Array.isArray(template?.tags) ? template.tags.filter((item: any) => typeof item === 'string') : [],
    isEditable: template?.isEditable !== false && !(template?.origin?.isLocked),
    isLocked: Boolean(template?.origin?.isLocked || template?.isStarter || template?.starterKey),
  } : null);
  setActiveTemplateFingerprint(
    templateId
      ? buildWorkflowStructureFingerprint(
        nodesWithSampleResult as Node<WorkflowNodeData>[],
        templateEdges as Edge[],
      )
      : null
  );
  if (templateSampleHasResult) {
    setFinalResult(mergedTemplateSampleResult);
    setFinalError(null);
    setFinalCompletedAt(templateSampleUpdatedAt || Date.now());
    setFinalRuntime(templateSampleRuntime);
    setFinalRuntimeHints(templateSampleRuntimeHints);
  } else {
    setFinalResult(null);
    setFinalError(null);
    setFinalCompletedAt(null);
    setFinalRuntime('');
    setFinalRuntimeHints([]);
  }
  if (requiresImageTemplate && !templateHasUsableImage) {
    addLog('system', '系统', 'warn', '该模板需要参考图片，请先上传图片或填写 input.imageUrl。');
  }
  setShowTemplateSelector(false);
  setPendingFitToken(`template-${Date.now()}`);
  addLog('system', '系统', 'info', `已加载模板: ${template.name}${templateSampleHasResult ? '（已同步最近结果）' : ''}`);
};
