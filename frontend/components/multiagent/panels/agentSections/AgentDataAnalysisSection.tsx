/**
 * Agent 节点数据分析参数面板。
 *
 * 1:1 抽离自 `AgentNodeConfigPanel.tsx` 数据分析 IIFE
 * （< 800 行合规拆分）。
 */

import React from 'react';
import { FileSpreadsheet, Upload, X } from 'lucide-react';
import { CustomNodeData } from '../../CustomNode';
import { fileToBase64 } from '../../../../hooks/handlers/attachmentUtils';
import { reportError } from '../../../../utils/globalErrorHandler';

export interface AgentDataAnalysisSectionProps {
  nodeData: CustomNodeData;
  updateNodeData: (patch: Partial<CustomNodeData>) => void;
}

export const AgentDataAnalysisSection: React.FC<AgentDataAnalysisSectionProps> = ({
  nodeData,
  updateNodeData,
}) => {
            const _hasFile = !!nodeData.agentFileUrl;
            const _fileName = nodeData.agentFileUrl?.startsWith('data:')
              ? '已上传文件'
              : nodeData.agentFileUrl || '';
            return (
              <div className="space-y-3 p-2.5 rounded-lg border border-cyan-500/20 bg-cyan-500/5">
                <div className="text-xs text-cyan-300 font-medium">数据分析参数</div>
                {/* 文件上传 */}
                <div>
                  <label className="block text-xs text-slate-500 mb-1">
                    数据文件 <span className="text-red-400">*</span>
                  </label>
                  {_hasFile && (
                    <div className="mb-2 flex items-center gap-2 px-2.5 py-1.5 bg-slate-800 rounded border border-cyan-500/30">
                      <FileSpreadsheet size={14} className="text-cyan-400 flex-shrink-0" />
                      <span className="text-[10px] text-slate-300 truncate flex-1">
                        {_fileName}
                      </span>
                      <button
                        onClick={() => updateNodeData({ agentFileUrl: '' })}
                        className="p-0.5 hover:bg-red-500/20 rounded text-red-400"
                      >
                        <X size={10} />
                      </button>
                    </div>
                  )}
                  <label className="flex items-center justify-center gap-1.5 px-3 py-2 bg-slate-800 border border-dashed border-cyan-500/40 rounded-lg cursor-pointer hover:border-cyan-500/60 transition-colors">
                    <Upload size={12} className="text-cyan-400" />
                    <span className="text-xs text-cyan-300">
                      {_hasFile ? '更换文件' : '上传文件'}
                    </span>
                    <input
                      type="file"
                      accept=".csv,.xlsx,.xls,.json,.tsv,.txt"
                      className="hidden"
                      onChange={async (e) => {
                        const f = e.target.files?.[0];
                        if (!f) return;
                        try {
                          updateNodeData({ agentFileUrl: await fileToBase64(f) });
                        } catch {
                          /* ignore */
                        }
                        e.target.value = '';
                      }}
                    />
                  </label>
                  <input
                    type="text"
                    value={
                      !nodeData.agentFileUrl?.startsWith('data:') ? nodeData.agentFileUrl || '' : ''
                    }
                    onChange={(e) => updateNodeData({ agentFileUrl: e.target.value })}
                    data-field-key="agentFileUrl"
                    className="mt-1.5 w-full px-2 py-1 bg-slate-800 border border-slate-700 rounded text-[10px] text-slate-400 font-mono focus:outline-none focus:border-cyan-500/50"
                    placeholder="或输入 URL / {{prev.output.fileUrl}}"
                  />
                  <div className="mt-1 text-[10px] text-slate-600">
                    支持 Excel / CSV / JSON / TSV 文件
                  </div>
                </div>
                {/* 输出格式 */}
                <div>
                  <label className="block text-xs text-slate-500 mb-1">输出格式</label>
                  <select
                    value={nodeData.agentOutputFormat || ''}
                    onChange={(e) => updateNodeData({ agentOutputFormat: e.target.value })}
                    data-field-key="agentOutputFormat"
                    className="w-full px-2 py-1.5 bg-slate-800 border border-slate-700 rounded text-xs text-slate-200 focus:outline-none focus:border-teal-500/50"
                  >
                    <option value="">默认（文本）</option>
                    <option value="text">纯文本</option>
                    <option value="json">JSON</option>
                    <option value="markdown">Markdown 表格</option>
                  </select>
                </div>
              </div>
            );
};
