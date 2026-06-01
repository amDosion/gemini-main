/**
 * Multi-agent 节点属性面板的"执行结果"区域。
 *
 * 1:1 抽离自 `PropertiesPanel.tsx` L197-317
 * （JIRA-frontend-view-decomposition.md P0 #1 Step 4）。
 *
 * 渲染：输入参考图 + 输出图/视频/音频列表 + 文本预览 + 原始结构化结果 details。
 * 仅在 status 非 'pending' 且 nodeData.result 存在时渲染（否则 null）。
 */

import React from 'react';
import type { CustomNodeData } from '../CustomNode';
import type { NodeStatus } from '../types';
import { CachedImage } from '../../common/CachedImage';
import { RetainedAudio, RetainedVideo } from '../../common/RetainedMedia';

export interface PropertiesPanelResultSectionProps {
  nodeData: CustomNodeData;
  selectedNodeId: string;
  sourcePreviewUrl: string | null;
  resultPreviewUrls: string[];
  resultPreviewAudioUrls: string[];
  resultPreviewVideoUrls: string[];
  resultPreviewText: string;
  status: NodeStatus;
}

export const PropertiesPanelResultSection: React.FC<PropertiesPanelResultSectionProps> = ({
  nodeData,
  selectedNodeId,
  sourcePreviewUrl,
  resultPreviewUrls,
  resultPreviewAudioUrls,
  resultPreviewVideoUrls,
  resultPreviewText,
  status,
}) => {
  if (status === 'pending' || !nodeData.result) {
    return null;
  }

  return (
    <div>
      <label className="block text-xs text-slate-500 mb-1.5">执行结果</label>
      <div
        className={`p-3 rounded-lg border ${
          status === 'failed'
            ? 'bg-red-500/5 border-red-500/20'
            : 'bg-emerald-500/5 border-emerald-500/20'
        }`}
      >
        {(sourcePreviewUrl || resultPreviewUrls.length > 0) && (
          <div className="mb-3 grid grid-cols-2 gap-2">
            {sourcePreviewUrl && (
              <div>
                <div className="text-[10px] text-slate-400 mb-1">输入参考图</div>
                <CachedImage
                  source={{
                    attachmentId: `${selectedNodeId}-source-preview`,
                    url: sourcePreviewUrl,
                    mimeType: 'image/png',
                    name: 'source-preview.png',
                  }}
                  src={sourcePreviewUrl}
                  alt="source-preview"
                  className="w-full h-24 object-contain rounded border border-slate-700 bg-slate-900"
                />
              </div>
            )}
            {resultPreviewUrls.length > 0 && (
              <div>
                <div className="text-[10px] text-slate-400 mb-1">
                  输出结果图（{resultPreviewUrls.length}）
                </div>
                <div className="grid grid-cols-2 gap-1 max-h-44 overflow-y-auto pr-0.5">
                  {resultPreviewUrls.map((imageUrl, index) => (
                    <CachedImage
                      key={`${selectedNodeId}-result-preview-${index}`}
                      source={{
                        attachmentId: `${selectedNodeId}-result-preview-${index}`,
                        url: imageUrl,
                        mimeType: 'image/png',
                        name: `result-preview-${index + 1}.png`,
                      }}
                      src={imageUrl}
                      alt={`result-preview-${index + 1}`}
                      className="w-full h-24 object-cover rounded border border-slate-700 bg-slate-900"
                    />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
        {(resultPreviewVideoUrls.length > 0 || resultPreviewAudioUrls.length > 0) && (
          <div className="mb-3 space-y-2">
            {resultPreviewVideoUrls.length > 0 && (
              <div>
                <div className="text-[10px] text-slate-400 mb-1">
                  输出视频（{resultPreviewVideoUrls.length}）
                </div>
                <div className="space-y-2 max-h-52 overflow-y-auto pr-0.5">
                  {resultPreviewVideoUrls.map((videoUrl, index) => (
                    <RetainedVideo
                      key={`${selectedNodeId}-result-video-${index}`}
                      src={videoUrl}
                      controls
                      className="w-full rounded border border-slate-700 bg-slate-900"
                    />
                  ))}
                </div>
              </div>
            )}
            {resultPreviewAudioUrls.length > 0 && (
              <div>
                <div className="text-[10px] text-slate-400 mb-1">
                  输出音频（{resultPreviewAudioUrls.length}）
                </div>
                <div className="space-y-2 max-h-40 overflow-y-auto pr-0.5">
                  {resultPreviewAudioUrls.map((audioUrl, index) => (
                    <RetainedAudio
                      key={`${selectedNodeId}-result-audio-${index}`}
                      src={audioUrl}
                      controls
                      className="w-full"
                    />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
        <pre className="text-[11px] text-slate-300 whitespace-pre-wrap break-words max-h-[220px] overflow-y-auto">
          {resultPreviewText || '（无可读文本结果）'}
        </pre>
        {typeof nodeData.result !== 'string' && (
          <details className="mt-2">
            <summary className="text-[10px] text-slate-500 cursor-pointer hover:text-slate-400">
              查看原始结构化结果
            </summary>
            <pre className="mt-1 text-[10px] text-slate-400 whitespace-pre-wrap break-words max-h-[180px] overflow-y-auto">
              {JSON.stringify(nodeData.result, null, 2)}
            </pre>
          </details>
        )}
      </div>
    </div>
  );
};
