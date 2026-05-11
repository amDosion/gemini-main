/**
 * Multi-agent workflow Start / Input 节点配置面板。
 *
 * 1:1 抽离自 `PropertiesPanel.tsx` renderStartInputNodeConfig L321-821
 * （JIRA-frontend-properties-panel-deep-split.md Step 3）。
 *
 * 覆盖 6 个节点类型：start / input_text / input_image / input_video /
 * input_audio / input_file。
 *
 * 闭包依赖（3 个 props）：nodeData / nodeType / updateNodeData。
 */

import React from 'react';
import { Node } from 'reactflow';
import { FileSpreadsheet, Image as ImageIcon, Mic, Upload, Video, X } from 'lucide-react';
import { CustomNodeData } from '../CustomNode';
import { NodeType } from '../nodeTypeConfigs';
import {
  reportInlineUploadError,
  readInlineFilesAsDataUrls,
} from '../uploadHandlers';
import { isDirectlyRenderableImageUrl } from '../workflowResultUtils';
import { dispatchScopedWorkflowEvent } from '../workflowEditorUtils';

export interface StartInputNodeConfigPanelProps {
  nodeData: CustomNodeData;
  nodeType: NodeType;
  selectedNode: Node<CustomNodeData>;
  updateNodeData: (patch: Partial<CustomNodeData>) => void;
}

export const StartInputNodeConfigPanel: React.FC<StartInputNodeConfigPanelProps> = ({
  nodeData,
  nodeType,
  selectedNode,
  updateNodeData,
}) => {
    if (
      ['start', 'input_text', 'input_image', 'input_video', 'input_audio', 'input_file'].includes(
        nodeType
      )
    ) {
      const isStartNode = nodeType === 'start';
      const isTextInputNode = nodeType === 'input_text';
      const isImageInputNode = nodeType === 'input_image';
      const isVideoInputNode = nodeType === 'input_video';
      const isAudioInputNode = nodeType === 'input_audio';
      const isFileInputNode = nodeType === 'input_file';
      const normalizeUrlList = (value: unknown): string[] => {
        if (!Array.isArray(value)) return [];
        return value.map((item) => String(item || '').trim()).filter(Boolean);
      };
      const dedupeUrlList = (...sources: string[][]): string[] => {
        const deduped = new Set<string>();
        const result: string[] = [];
        sources.forEach((source) => {
          source.forEach((item) => {
            if (!deduped.has(item)) {
              deduped.add(item);
              result.push(item);
            }
          });
        });
        return result;
      };
      const parseUrlTextareaValue = (rawValue: string): string[] => {
        return Array.from(
          new Set(
            String(rawValue || '')
              .split(/\r?\n/)
              .map((item) => item.trim())
              .filter(Boolean)
          )
        );
      };

      const startImageValues = dedupeUrlList(
        normalizeUrlList(nodeData.startImageUrls),
        nodeData.startImageUrl ? [String(nodeData.startImageUrl).trim()] : []
      );
      const startVideoValues = dedupeUrlList(
        normalizeUrlList(nodeData.startVideoUrls),
        nodeData.startVideoUrl ? [String(nodeData.startVideoUrl).trim()] : []
      );
      const startAudioValues = dedupeUrlList(
        normalizeUrlList(nodeData.startAudioUrls),
        nodeData.startAudioUrl ? [String(nodeData.startAudioUrl).trim()] : []
      );
      const startFileValues = dedupeUrlList(
        normalizeUrlList(nodeData.startFileUrls),
        nodeData.startFileUrl ? [String(nodeData.startFileUrl).trim()] : []
      );
      const hasStartImage = startImageValues.length > 0;
      const hasStartVideo = startVideoValues.length > 0;
      const hasStartAudio = startAudioValues.length > 0;
      const hasStartFile = startFileValues.length > 0;
      const renderableStartImageValues = startImageValues.filter(
        (value) => value.startsWith('data:') || isDirectlyRenderableImageUrl(value)
      );
      const startImageTextAreaValue = startImageValues
        .filter((value) => !value.startsWith('data:'))
        .join('\n');
      const startVideoTextAreaValue = startVideoValues
        .filter((value) => !value.startsWith('data:'))
        .join('\n');
      const startAudioTextAreaValue = startAudioValues
        .filter((value) => !value.startsWith('data:'))
        .join('\n');
      const startFileTextAreaValue = startFileValues
        .filter((value) => !value.startsWith('data:'))
        .join('\n');
      const title = isStartNode
        ? '开始入口配置'
        : isTextInputNode
          ? '文本输入组件'
          : isImageInputNode
            ? '图片输入组件'
            : isVideoInputNode
              ? '视频输入组件'
              : isAudioInputNode
                ? '音频输入组件'
                : '文件输入组件';
      const desc = isStartNode
        ? '开始节点按钮将从此处读取任务输入和媒体附件并启动工作流。'
        : isTextInputNode
          ? '注入任务文本到下游节点（覆盖 input.task）。'
          : isImageInputNode
            ? '注入图片地址到下游节点（input.imageUrl）。'
            : isVideoInputNode
              ? '注入视频地址到下游节点（input.videoUrl）。'
              : isAudioInputNode
                ? '注入音频地址到下游节点（input.audioUrl）。'
                : '注入文件地址到下游节点（input.fileUrl）。';

      return (
        <div className="space-y-4">
          <div className="p-2.5 rounded-lg border border-emerald-500/20 bg-emerald-500/5">
            <div className="text-xs text-emerald-300 font-medium">{title}</div>
            <div className="mt-1 text-[10px] text-slate-500">{desc}</div>
          </div>

          {(isStartNode || isTextInputNode) && (
            <div>
              <label className="block text-xs text-slate-500 mb-1.5">任务输入（input.task）</label>
              <textarea
                value={nodeData.startTask || ''}
                onChange={(e) => updateNodeData({ startTask: e.target.value })}
                rows={3}
                data-field-key="startTask"
                className="w-full px-3 py-2 bg-slate-800 border border-slate-700 rounded-lg text-xs text-slate-300 focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/20 resize-none"
                placeholder="输入提示词，或 JSON（例如包含 imageUrl / fileUrl）"
              />
            </div>
          )}

          {(isStartNode || isImageInputNode) && (
            <div className="space-y-2">
              <label className="block text-xs text-slate-500">
                输入图片（input.imageUrl / input.imageUrls）
              </label>
              {renderableStartImageValues.length > 0 && (
                <div className="grid grid-cols-4 gap-2 max-h-56 overflow-y-auto pr-1">
                  {renderableStartImageValues.map((imageUrl, index) => (
                    <div key={`${selectedNode.id}-input-image-${index}`} className="relative group">
                      <img
                        src={imageUrl}
                        alt={`输入图片-${index + 1}`}
                        className="w-full h-16 object-cover rounded border border-emerald-500/30"
                      />
                      <button
                        onClick={() => {
                          const removeIndex = startImageValues.findIndex(
                            (value) => value === imageUrl
                          );
                          const nextValues = startImageValues.filter(
                            (_, sourceIndex) => sourceIndex !== removeIndex
                          );
                          updateNodeData({
                            startImageUrl: nextValues[0] || '',
                            startImageUrls: nextValues,
                          });
                        }}
                        className="absolute top-1 right-1 p-0.5 bg-red-500/80 rounded-full text-white opacity-0 group-hover:opacity-100 transition-opacity"
                      >
                        <X size={10} />
                      </button>
                    </div>
                  ))}
                </div>
              )}
              {hasStartImage && (
                <button
                  type="button"
                  onClick={() => updateNodeData({ startImageUrl: '', startImageUrls: [] })}
                  className="w-full px-2 py-1 text-[11px] rounded border border-red-500/30 bg-red-500/10 text-red-300 hover:bg-red-500/20 transition-colors"
                >
                  清空全部图片
                </button>
              )}
              <label className="flex items-center justify-center gap-1.5 px-3 py-2 bg-slate-800 border border-dashed border-emerald-500/40 rounded-lg cursor-pointer hover:border-emerald-500/60 transition-colors">
                <Upload size={12} className="text-emerald-400" />
                <ImageIcon size={12} className="text-emerald-400" />
                <span className="text-xs text-emerald-300">
                  {hasStartImage ? '继续上传图片' : '上传图片'}
                </span>
                <input
                  type="file"
                  accept="image/*"
                  multiple
                  className="hidden"
                  onChange={async (e) => {
                    const files = Array.from(e.target.files || []);
                    if (files.length === 0) return;
                    try {
                      const encoded = await readInlineFilesAsDataUrls(files, '输入节点图片');
                      const nextValues = dedupeUrlList(startImageValues, encoded);
                      updateNodeData({
                        startImageUrl: nextValues[0] || '',
                        startImageUrls: nextValues,
                      });
                    } catch (err) {
                      reportInlineUploadError('输入节点图片读取失败', err);
                    }
                    e.target.value = '';
                  }}
                />
              </label>
              <textarea
                value={startImageTextAreaValue}
                onChange={(e) => {
                  const dataUrls = startImageValues.filter((value) => value.startsWith('data:'));
                  const textUrls = parseUrlTextareaValue(e.target.value);
                  const nextValues = dedupeUrlList(dataUrls, textUrls);
                  updateNodeData({
                    startImageUrl: nextValues[0] || '',
                    startImageUrls: nextValues,
                  });
                }}
                rows={3}
                data-field-key="startImageUrls"
                className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-[10px] text-slate-300 font-mono focus:outline-none focus:border-emerald-500/50 resize-y"
                placeholder={'每行一个图片URL\nhttps://... \n{{prev.output.imageUrl}}'}
              />
              <input type="hidden" data-field-key="startImageUrl" value="" readOnly />
            </div>
          )}

          {(isStartNode || isVideoInputNode) && (
            <div className="space-y-2">
              <label className="block text-xs text-slate-500">
                输入视频（input.videoUrl / input.videoUrls）
              </label>
              {hasStartVideo && (
                <div className="space-y-1 max-h-40 overflow-y-auto pr-1">
                  {startVideoValues.map((videoUrl, index) => (
                    <div
                      key={`${selectedNode.id}-input-video-${index}`}
                      className="flex items-center gap-2 px-2.5 py-1.5 bg-slate-800 rounded border border-indigo-500/30"
                    >
                      <Video size={14} className="text-indigo-400 flex-shrink-0" />
                      <span className="text-[10px] text-slate-300 truncate flex-1">
                        {videoUrl.startsWith('data:') ? `已上传视频 ${index + 1}` : videoUrl}
                      </span>
                      <button
                        onClick={() => {
                          const nextValues = startVideoValues.filter(
                            (_, sourceIndex) => sourceIndex !== index
                          );
                          updateNodeData({
                            startVideoUrl: nextValues[0] || '',
                            startVideoUrls: nextValues,
                          });
                        }}
                        className="p-0.5 hover:bg-red-500/20 rounded text-red-400"
                      >
                        <X size={10} />
                      </button>
                    </div>
                  ))}
                </div>
              )}
              {hasStartVideo && (
                <button
                  type="button"
                  onClick={() => updateNodeData({ startVideoUrl: '', startVideoUrls: [] })}
                  className="w-full px-2 py-1 text-[11px] rounded border border-red-500/30 bg-red-500/10 text-red-300 hover:bg-red-500/20 transition-colors"
                >
                  清空全部视频
                </button>
              )}
              <label className="flex items-center justify-center gap-1.5 px-3 py-2 bg-slate-800 border border-dashed border-indigo-500/40 rounded-lg cursor-pointer hover:border-indigo-500/60 transition-colors">
                <Upload size={12} className="text-indigo-400" />
                <Video size={12} className="text-indigo-400" />
                <span className="text-xs text-indigo-300">
                  {hasStartVideo ? '继续上传视频' : '上传视频'}
                </span>
                <input
                  type="file"
                  accept="video/*,.mp4,.mov,.webm,.avi,.mkv"
                  multiple
                  className="hidden"
                  onChange={async (e) => {
                    const files = Array.from(e.target.files || []);
                    if (files.length === 0) return;
                    try {
                      const encoded = await readInlineFilesAsDataUrls(files, '输入节点视频');
                      const nextValues = dedupeUrlList(startVideoValues, encoded);
                      updateNodeData({
                        startVideoUrl: nextValues[0] || '',
                        startVideoUrls: nextValues,
                      });
                    } catch (err) {
                      reportInlineUploadError('输入节点视频读取失败', err);
                    }
                    e.target.value = '';
                  }}
                />
              </label>
              <textarea
                value={startVideoTextAreaValue}
                onChange={(e) => {
                  const dataUrls = startVideoValues.filter((value) => value.startsWith('data:'));
                  const textUrls = parseUrlTextareaValue(e.target.value);
                  const nextValues = dedupeUrlList(dataUrls, textUrls);
                  updateNodeData({
                    startVideoUrl: nextValues[0] || '',
                    startVideoUrls: nextValues,
                  });
                }}
                rows={3}
                data-field-key="startVideoUrls"
                className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-[10px] text-slate-300 font-mono focus:outline-none focus:border-indigo-500/50 resize-y"
                placeholder={'每行一个视频URL\nhttps://... \n{{prev.output.videoUrl}}'}
              />
              <input type="hidden" data-field-key="startVideoUrl" value="" readOnly />
            </div>
          )}

          {(isStartNode || isAudioInputNode) && (
            <div className="space-y-2">
              <label className="block text-xs text-slate-500">
                输入音频（input.audioUrl / input.audioUrls）
              </label>
              {hasStartAudio && (
                <div className="space-y-1 max-h-40 overflow-y-auto pr-1">
                  {startAudioValues.map((audioUrl, index) => (
                    <div
                      key={`${selectedNode.id}-input-audio-${index}`}
                      className="flex items-center gap-2 px-2.5 py-1.5 bg-slate-800 rounded border border-sky-500/30"
                    >
                      <Mic size={14} className="text-sky-400 flex-shrink-0" />
                      <span className="text-[10px] text-slate-300 truncate flex-1">
                        {audioUrl.startsWith('data:') ? `已上传音频 ${index + 1}` : audioUrl}
                      </span>
                      <button
                        onClick={() => {
                          const nextValues = startAudioValues.filter(
                            (_, sourceIndex) => sourceIndex !== index
                          );
                          updateNodeData({
                            startAudioUrl: nextValues[0] || '',
                            startAudioUrls: nextValues,
                          });
                        }}
                        className="p-0.5 hover:bg-red-500/20 rounded text-red-400"
                      >
                        <X size={10} />
                      </button>
                    </div>
                  ))}
                </div>
              )}
              {hasStartAudio && (
                <button
                  type="button"
                  onClick={() => updateNodeData({ startAudioUrl: '', startAudioUrls: [] })}
                  className="w-full px-2 py-1 text-[11px] rounded border border-red-500/30 bg-red-500/10 text-red-300 hover:bg-red-500/20 transition-colors"
                >
                  清空全部音频
                </button>
              )}
              <label className="flex items-center justify-center gap-1.5 px-3 py-2 bg-slate-800 border border-dashed border-sky-500/40 rounded-lg cursor-pointer hover:border-sky-500/60 transition-colors">
                <Upload size={12} className="text-sky-400" />
                <Mic size={12} className="text-sky-400" />
                <span className="text-xs text-sky-300">
                  {hasStartAudio ? '继续上传音频' : '上传音频'}
                </span>
                <input
                  type="file"
                  accept="audio/*,.mp3,.wav,.m4a,.aac,.flac,.ogg,.opus"
                  multiple
                  className="hidden"
                  onChange={async (e) => {
                    const files = Array.from(e.target.files || []);
                    if (files.length === 0) return;
                    try {
                      const encoded = await readInlineFilesAsDataUrls(files, '输入节点音频');
                      const nextValues = dedupeUrlList(startAudioValues, encoded);
                      updateNodeData({
                        startAudioUrl: nextValues[0] || '',
                        startAudioUrls: nextValues,
                      });
                    } catch (err) {
                      reportInlineUploadError('输入节点音频读取失败', err);
                    }
                    e.target.value = '';
                  }}
                />
              </label>
              <textarea
                value={startAudioTextAreaValue}
                onChange={(e) => {
                  const dataUrls = startAudioValues.filter((value) => value.startsWith('data:'));
                  const textUrls = parseUrlTextareaValue(e.target.value);
                  const nextValues = dedupeUrlList(dataUrls, textUrls);
                  updateNodeData({
                    startAudioUrl: nextValues[0] || '',
                    startAudioUrls: nextValues,
                  });
                }}
                rows={3}
                data-field-key="startAudioUrls"
                className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-[10px] text-slate-300 font-mono focus:outline-none focus:border-sky-500/50 resize-y"
                placeholder={'每行一个音频URL\nhttps://... \n{{prev.output.audioUrl}}'}
              />
              <input type="hidden" data-field-key="startAudioUrl" value="" readOnly />
            </div>
          )}

          {(isStartNode || isFileInputNode) && (
            <div className="space-y-2">
              <label className="block text-xs text-slate-500">
                输入文件（input.fileUrl / input.fileUrls）
              </label>
              {hasStartFile && (
                <div className="space-y-1 max-h-40 overflow-y-auto pr-1">
                  {startFileValues.map((fileUrl, index) => (
                    <div
                      key={`${selectedNode.id}-input-file-${index}`}
                      className="flex items-center gap-2 px-2.5 py-1.5 bg-slate-800 rounded border border-cyan-500/30"
                    >
                      <FileSpreadsheet size={14} className="text-cyan-400 flex-shrink-0" />
                      <span className="text-[10px] text-slate-300 truncate flex-1">
                        {fileUrl.startsWith('data:') ? `已上传文件 ${index + 1}` : fileUrl}
                      </span>
                      <button
                        onClick={() => {
                          const nextValues = startFileValues.filter(
                            (_, sourceIndex) => sourceIndex !== index
                          );
                          updateNodeData({
                            startFileUrl: nextValues[0] || '',
                            startFileUrls: nextValues,
                          });
                        }}
                        className="p-0.5 hover:bg-red-500/20 rounded text-red-400"
                      >
                        <X size={10} />
                      </button>
                    </div>
                  ))}
                </div>
              )}
              {hasStartFile && (
                <button
                  type="button"
                  onClick={() => updateNodeData({ startFileUrl: '', startFileUrls: [] })}
                  className="w-full px-2 py-1 text-[11px] rounded border border-red-500/30 bg-red-500/10 text-red-300 hover:bg-red-500/20 transition-colors"
                >
                  清空全部文件
                </button>
              )}
              <label className="flex items-center justify-center gap-1.5 px-3 py-2 bg-slate-800 border border-dashed border-cyan-500/40 rounded-lg cursor-pointer hover:border-cyan-500/60 transition-colors">
                <Upload size={12} className="text-cyan-400" />
                <FileSpreadsheet size={12} className="text-cyan-400" />
                <span className="text-xs text-cyan-300">
                  {hasStartFile ? '继续上传文件' : '上传文件'}
                </span>
                <input
                  type="file"
                  accept=".csv,.xlsx,.xls,.json,.tsv,.txt,.pdf"
                  multiple
                  className="hidden"
                  onChange={async (e) => {
                    const files = Array.from(e.target.files || []);
                    if (files.length === 0) return;
                    try {
                      const encoded = await readInlineFilesAsDataUrls(files, '输入节点文件');
                      const nextValues = dedupeUrlList(startFileValues, encoded);
                      updateNodeData({
                        startFileUrl: nextValues[0] || '',
                        startFileUrls: nextValues,
                      });
                    } catch (err) {
                      reportInlineUploadError('输入节点文件读取失败', err);
                    }
                    e.target.value = '';
                  }}
                />
              </label>
              <textarea
                value={startFileTextAreaValue}
                onChange={(e) => {
                  const dataUrls = startFileValues.filter((value) => value.startsWith('data:'));
                  const textUrls = parseUrlTextareaValue(e.target.value);
                  const nextValues = dedupeUrlList(dataUrls, textUrls);
                  updateNodeData({
                    startFileUrl: nextValues[0] || '',
                    startFileUrls: nextValues,
                  });
                }}
                rows={3}
                data-field-key="startFileUrls"
                className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-[10px] text-slate-300 font-mono focus:outline-none focus:border-cyan-500/50 resize-y"
                placeholder={'每行一个文件URL\nhttps://... \n{{prev.output.fileUrl}}'}
              />
              <input type="hidden" data-field-key="startFileUrl" value="" readOnly />
            </div>
          )}

          {isStartNode && (
            <button
              onClick={(event) => {
                dispatchScopedWorkflowEvent('workflow:execute-request', event.currentTarget, {
                  nodeId: String(selectedNode.id),
                });
              }}
              className="w-full px-3 py-2 text-xs rounded-lg border border-emerald-500/40 bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20 transition-colors"
            >
              使用开始按钮执行工作流
            </button>
          )}
        </div>
      );
    }

    return null;
};
