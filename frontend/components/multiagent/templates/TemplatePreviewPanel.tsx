/**
 * Template Preview panel (right half of content area)
 *
 * 1:1 抽离自 `WorkflowTemplateSelector.tsx` L862-1188
 * （< 800 行合规拆分）。
 *
 * 负责渲染：
 * - 模板标题（含 inline rename 状态）+ 描述
 * - origin/runtime/tags 徽标
 * - Starter / 来源 / 遗留副本三类提示横幅
 * - 工作流结构数据（节点/连接/绑定方式）
 * - prompt 建议
 * - 模板最近结果（图片/视频/音频/文本预览/runtime 元数据）
 * - 节点列表 + 创建/更新时间
 * - copy / template action feedback
 * - selectedTemplate 为空时的空状态
 */

import React from 'react';
import { Loader2, Mic, Pencil, Save, Video, FileText } from 'lucide-react';
import {
  type WorkflowTemplate,
  resolveTemplateOriginLabel,
  resolveTemplateRuntimeLabel,
} from '../workflowTemplateTypes';
import { CachedImage } from '../../common/CachedImage';
import { RetainedAudio, RetainedVideo } from '../../common/RetainedMedia';

interface TemplatePreviewPanelProps {
  selectedTemplate: WorkflowTemplate | null;
  editingTemplateId: string | null;
  editingTemplateName: string;
  setEditingTemplateName: React.Dispatch<React.SetStateAction<string>>;
  savingTemplateId: string | null;
  handleSaveTemplateTitle: () => void;
  handleCancelRenameTemplate: () => void;
  handleStartRenameTemplate: () => void;
  canManageTemplate: (template: WorkflowTemplate | null) => boolean;
  selectedTemplateHasSampleResult: boolean;
  selectedTemplateSampleImageUrls: string[];
  selectedTemplateSampleVideoUrls: string[];
  selectedTemplateSampleAudioUrls: string[];
  selectedTemplateSampleTextPreview: string;
  copyFeedback: string | null;
  templateActionFeedback: string | null;
}

export const TemplatePreviewPanel: React.FC<TemplatePreviewPanelProps> = ({
  selectedTemplate,
  editingTemplateId,
  editingTemplateName,
  setEditingTemplateName,
  savingTemplateId,
  handleSaveTemplateTitle,
  handleCancelRenameTemplate,
  handleStartRenameTemplate,
  canManageTemplate,
  selectedTemplateHasSampleResult,
  selectedTemplateSampleImageUrls,
  selectedTemplateSampleVideoUrls,
  selectedTemplateSampleAudioUrls,
  selectedTemplateSampleTextPreview,
  copyFeedback,
  templateActionFeedback,
}) => {
  const runtimeLabel = selectedTemplate ? resolveTemplateRuntimeLabel(selectedTemplate) : '';
  const canManageSelected = canManageTemplate(selectedTemplate);
  return (
    <div className="w-1/2 overflow-y-auto bg-slate-900/40">
      {selectedTemplate ? (
        <div className="p-6 space-y-4">
          <div>
            {editingTemplateId === selectedTemplate.id ? (
              <div className="flex items-start gap-2 mb-2">
                <input
                  type="text"
                  value={editingTemplateName}
                  onChange={(event) => setEditingTemplateName(event.target.value)}
                  className="flex-1 px-3 py-2 border border-slate-700 rounded-lg bg-slate-800 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-teal-500/30 focus:border-teal-500/50"
                  placeholder="输入模板标题"
                />
                <button
                  onClick={handleSaveTemplateTitle}
                  disabled={savingTemplateId === selectedTemplate.id}
                  className="px-3 py-2 text-xs bg-emerald-600 text-white rounded-lg hover:bg-emerald-500 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
                  title="保存标题"
                >
                  {savingTemplateId === selectedTemplate.id ? (
                    <Loader2 size={13} className="animate-spin" />
                  ) : (
                    <Save size={13} />
                  )}
                  保存
                </button>
                <button
                  onClick={handleCancelRenameTemplate}
                  disabled={savingTemplateId === selectedTemplate.id}
                  className="px-3 py-2 text-xs bg-slate-800 border border-slate-700 text-slate-300 rounded-lg hover:bg-slate-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                  title="取消编辑"
                >
                  取消
                </button>
              </div>
            ) : (
              <div className="flex items-start justify-between gap-2 mb-2">
                <h3 className="text-lg font-semibold text-slate-100">{selectedTemplate.name}</h3>
                <button
                  onClick={handleStartRenameTemplate}
                  disabled={!canManageSelected}
                  className="px-2.5 py-1.5 text-xs bg-slate-800 border border-slate-700 text-slate-300 rounded-lg hover:bg-slate-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
                  title={canManageSelected ? '编辑模板标题' : '只读模板不可编辑'}
                >
                  <Pencil size={13} />
                  编辑标题
                </button>
              </div>
            )}
            <p className="text-sm text-slate-400">{selectedTemplate.description}</p>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs px-2 py-1 bg-teal-500/20 text-teal-200 border border-teal-500/30 rounded font-medium">
              {selectedTemplate.category}
            </span>
            <span className="text-xs px-2 py-1 bg-slate-900 text-slate-200 border border-slate-700 rounded">
              {resolveTemplateOriginLabel(selectedTemplate)}
            </span>
            {runtimeLabel && (
              <span className="text-xs px-2 py-1 bg-amber-500/10 text-amber-200 border border-amber-500/20 rounded">
                {runtimeLabel}
              </span>
            )}
            {selectedTemplate.tags.map((tag) => (
              <span
                key={tag}
                className="text-xs px-2 py-1 bg-slate-800 text-slate-300 border border-slate-700 rounded"
              >
                {tag}
              </span>
            ))}
          </div>

          {selectedTemplate.origin?.isLocked && (
            <div className="p-3 rounded-lg border border-amber-500/30 bg-amber-500/10 text-xs text-amber-100">
              这是官方 Starter 模板。建议先复制后再编辑，系统会持续按 starter catalog 维护这类模板。
            </div>
          )}
          {selectedTemplate.copiedFromStarterKey && !selectedTemplate.origin?.isLocked && (
            <div className="p-3 rounded-lg border border-slate-700 bg-slate-950/60 text-xs text-slate-300">
              当前模板来自 starter：
              <span className="text-slate-100">{selectedTemplate.copiedFromStarterKey}</span>
            </div>
          )}
          {selectedTemplate.isLegacyStarterCopy && (
            <div className="p-3 rounded-lg border border-amber-500/30 bg-amber-500/10 text-xs text-amber-100">
              这是遗留 Starter 副本：仍嵌入旧版 inline Agent 定义。建议复制官方新版 Starter，或改成
              `agentId / agentName` 绑定统一 Agent。
            </div>
          )}

          <div className="pt-4 border-t border-slate-700">
            <h4 className="text-sm font-semibold text-slate-200 mb-3">工作流结构</h4>
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-400">节点数量</span>
                <span className="font-medium text-slate-200">
                  {selectedTemplate.config.nodes.length || selectedTemplate.estimatedNodeCount || 0}
                </span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-slate-400">连接数量</span>
                <span className="font-medium text-slate-200">
                  {selectedTemplate.config.edges.length || selectedTemplate.estimatedEdgeCount || 0}
                </span>
              </div>
              {selectedTemplate.bindingStrategy && (
                <div className="flex items-center justify-between text-sm">
                  <span className="text-slate-400">绑定方式</span>
                  <span className="font-medium text-slate-200">
                    {selectedTemplate.bindingStrategy}
                  </span>
                </div>
              )}
            </div>
          </div>

          {(selectedTemplate.promptHint || selectedTemplate.promptExample) && (
            <div className="pt-4 border-t border-slate-700">
              <h4 className="text-sm font-semibold text-slate-200 mb-2">输入建议</h4>
              {selectedTemplate.promptHint && (
                <div className="text-xs text-slate-400 mb-2">{selectedTemplate.promptHint}</div>
              )}
              {selectedTemplate.promptExample && (
                <pre className="text-[11px] text-slate-300 bg-slate-950/80 border border-slate-700 rounded p-2 whitespace-pre-wrap break-all">
                  {typeof selectedTemplate.promptExample === 'string'
                    ? selectedTemplate.promptExample
                    : JSON.stringify(selectedTemplate.promptExample, null, 2)}
                </pre>
              )}
              {selectedTemplate.requiresImage && (
                <div className="mt-2 text-[11px] text-amber-300">
                  该流程需要输入参考图片（imageUrl）。
                </div>
              )}
            </div>
          )}

          <div className="pt-4 border-t border-slate-700">
            <div className="flex items-center justify-between mb-2">
              <h4 className="text-sm font-semibold text-slate-200">模板最近结果</h4>
              {selectedTemplate.sampleResultUpdatedAt && (
                <span className="text-[11px] text-slate-500">
                  {new Date(selectedTemplate.sampleResultUpdatedAt).toLocaleString()}
                </span>
              )}
            </div>
            {selectedTemplateHasSampleResult ? (
              <div className="space-y-2">
                {selectedTemplateSampleImageUrls.length > 0 && (
                  <div
                    className={`grid gap-2 ${selectedTemplateSampleImageUrls.length > 1 ? 'grid-cols-2' : 'grid-cols-1'}`}
                  >
                    {selectedTemplateSampleImageUrls.map((imageUrl, index) => (
                      <CachedImage
                        key={`${selectedTemplate.id}-sample-image-${index}`}
                        source={{ url: imageUrl, name: `template-sample-${index + 1}` }}
                        src={imageUrl}
                        alt={`template-sample-${index + 1}`}
                        className="w-full h-24 rounded border border-slate-700 object-cover bg-slate-950/70"
                      />
                    ))}
                  </div>
                )}
                {selectedTemplateSampleVideoUrls.length > 0 && (
                  <div className="space-y-2">
                    <div className="text-xs text-slate-400 inline-flex items-center gap-1">
                      <Video size={12} />
                      视频结果（{selectedTemplateSampleVideoUrls.length}）
                    </div>
                    <div className="space-y-2">
                      {selectedTemplateSampleVideoUrls.map((videoUrl, index) => (
                        <RetainedVideo
                          key={`${selectedTemplate.id}-sample-video-${index}`}
                          src={videoUrl}
                          controls
                          className="w-full rounded border border-slate-700 bg-slate-950/70"
                        />
                      ))}
                    </div>
                  </div>
                )}
                {selectedTemplateSampleAudioUrls.length > 0 && (
                  <div className="space-y-2">
                    <div className="text-xs text-slate-400 inline-flex items-center gap-1">
                      <Mic size={12} />
                      音频结果（{selectedTemplateSampleAudioUrls.length}）
                    </div>
                    <div className="space-y-2">
                      {selectedTemplateSampleAudioUrls.map((audioUrl, index) => (
                        <RetainedAudio
                          key={`${selectedTemplate.id}-sample-audio-${index}`}
                          src={audioUrl}
                          controls
                          className="w-full"
                        />
                      ))}
                    </div>
                  </div>
                )}
                {selectedTemplateSampleTextPreview && (
                  <pre className="text-[11px] text-slate-300 bg-slate-950/80 border border-slate-700 rounded p-2 whitespace-pre-wrap break-all max-h-[130px] overflow-y-auto">
                    {selectedTemplateSampleTextPreview}
                  </pre>
                )}
                {selectedTemplate.sampleResultSummary?.primaryRuntime && (
                  <div className="text-[11px] text-slate-500">
                    runtime: {selectedTemplate.sampleResultSummary.primaryRuntime}
                  </div>
                )}
                <div className="flex flex-wrap gap-1.5">
                  {((selectedTemplate.sampleResultSummary?.videoExtensionApplied || 0) > 0 ||
                    (selectedTemplate.sampleResultSummary?.videoExtensionCount || 0) > 0) && (
                    <span className="text-[11px] px-2 py-0.5 rounded border border-orange-500/30 bg-orange-500/10 text-orange-200">
                      延长{' '}
                      {selectedTemplate.sampleResultSummary?.videoExtensionApplied ||
                        selectedTemplate.sampleResultSummary?.videoExtensionCount}{' '}
                      次
                    </span>
                  )}
                  {(selectedTemplate.sampleResultSummary?.totalDurationSeconds || 0) > 0 && (
                    <span className="text-[11px] px-2 py-0.5 rounded border border-cyan-500/30 bg-cyan-500/10 text-cyan-200">
                      总时长 {selectedTemplate.sampleResultSummary?.totalDurationSeconds}s
                    </span>
                  )}
                  {(((selectedTemplate.sampleResultSummary?.subtitleMode || '') !== '' &&
                    selectedTemplate.sampleResultSummary?.subtitleMode !== 'none') ||
                    (selectedTemplate.sampleResultSummary?.subtitleFileCount || 0) > 0) && (
                    <span className="text-[11px] px-2 py-0.5 rounded border border-emerald-500/30 bg-emerald-500/10 text-emerald-200">
                      字幕
                      {(selectedTemplate.sampleResultSummary?.subtitleFileCount || 0) > 0
                        ? ` · ${selectedTemplate.sampleResultSummary?.subtitleFileCount}`
                        : ''}
                    </span>
                  )}
                  {(selectedTemplate.sampleResultSummary?.continuedFromVideo ||
                    Boolean(selectedTemplate.sampleResultSummary?.continuationStrategy)) && (
                    <span className="text-[11px] px-2 py-0.5 rounded border border-violet-500/30 bg-violet-500/10 text-violet-200">
                      {selectedTemplate.sampleResultSummary?.continuationStrategy ===
                      'video_extension_chain'
                        ? '官方续接'
                        : '视频续接'}
                    </span>
                  )}
                </div>
              </div>
            ) : (
              <div className="text-xs text-slate-500 border border-dashed border-slate-700 rounded p-2 bg-slate-800/30">
                暂无模板结果。加载并执行一次该模板后，会自动写入结果快照用于快速预览。
              </div>
            )}
          </div>

          <div className="pt-4 border-t border-slate-700">
            <h4 className="text-sm font-semibold text-slate-200 mb-3">节点列表</h4>
            <div className="space-y-2 max-h-[200px] overflow-y-auto">
              {selectedTemplate.config.nodes.length > 0 ? (
                selectedTemplate.config.nodes.map((node) => (
                  <div
                    key={node.id}
                    className="flex items-center gap-2 p-2 bg-slate-800/60 border border-slate-700 rounded text-sm"
                  >
                    <span className="text-lg">{node.data.icon}</span>
                    <div className="flex-1 min-w-0">
                      <div className="font-medium text-slate-100 truncate">{node.data.label}</div>
                      <div className="text-xs text-slate-500 truncate">{node.data.description}</div>
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-xs text-slate-500 p-2 border border-slate-700 rounded bg-slate-800/30">
                  模板未包含节点定义。
                </div>
              )}
            </div>
          </div>

          <div className="pt-4 text-xs text-slate-500">
            <div>创建时间: {new Date(selectedTemplate.createdAt).toLocaleString()}</div>
            <div>更新时间: {new Date(selectedTemplate.updatedAt).toLocaleString()}</div>
          </div>
          {copyFeedback && (
            <div
              className={`text-xs ${
                copyFeedback.startsWith('复制失败') ? 'text-rose-300' : 'text-emerald-300'
              }`}
            >
              {copyFeedback}
            </div>
          )}
          {templateActionFeedback && (
            <div
              className={`text-xs ${
                templateActionFeedback.startsWith('删除失败') ||
                templateActionFeedback.startsWith('更新失败')
                  ? 'text-rose-300'
                  : 'text-emerald-300'
              }`}
            >
              {templateActionFeedback}
            </div>
          )}
        </div>
      ) : (
        <div className="flex items-center justify-center h-full text-slate-500">
          <div className="text-center">
            <FileText size={48} className="mx-auto mb-2" />
            <p>选择一个模板查看详情</p>
          </div>
        </div>
      )}
    </div>
  );
};
