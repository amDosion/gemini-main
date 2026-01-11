/**
 * PDF 提取高级设置组件
 * 
 * 提供 PDF 提取的高级配置选项：
 * - 额外提取指令
 * - 输出格式选择（未来扩展）
 */
import React from 'react';
import { FileText, Info } from 'lucide-react';

interface PdfAdvancedSettingsProps {
  additionalInstructions: string;
  setAdditionalInstructions: (v: string) => void;
}

export const PdfAdvancedSettings: React.FC<PdfAdvancedSettingsProps> = ({
  additionalInstructions,
  setAdditionalInstructions
}) => {
  return (
    <div className="mb-3 p-4 bg-slate-900/50 border border-slate-700/50 rounded-2xl animate-[fadeIn_0.2s_ease-out]">
      <div className="flex items-center gap-2 mb-3">
        <FileText size={16} className="text-indigo-400" />
        <span className="text-sm font-medium text-slate-200">PDF 提取设置</span>
      </div>

      {/* 额外提取指令 */}
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <label className="text-xs text-slate-400">额外提取指令</label>
          <div className="group relative">
            <Info size={12} className="text-slate-500 cursor-help" />
            <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 px-3 py-2 bg-slate-800 border border-slate-600 rounded-lg text-xs text-slate-300 w-64 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50 shadow-xl">
              <p className="mb-1">添加额外的提取指令来细化结果。</p>
              <p className="text-slate-400">例如：</p>
              <ul className="text-slate-400 list-disc list-inside mt-1">
                <li>只提取金额大于100的项目</li>
                <li>将日期格式化为 YYYY-MM-DD</li>
                <li>忽略页眉和页脚内容</li>
              </ul>
            </div>
          </div>
        </div>
        <textarea
          value={additionalInstructions}
          onChange={(e) => setAdditionalInstructions(e.target.value)}
          placeholder="输入额外的提取指令（可选）..."
          className="w-full bg-slate-800/50 border border-slate-700 rounded-xl px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 resize-none"
          rows={2}
        />
      </div>

      {/* 提示信息 */}
      <div className="mt-3 p-2 bg-slate-800/30 rounded-lg">
        <p className="text-[10px] text-slate-500">
          💡 提示：选择合适的模板可以提高提取准确度。如果文档类型不在预设模板中，可以选择"全文提取"获取原始文本。
        </p>
      </div>
    </div>
  );
};
