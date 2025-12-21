import React from 'react';
import { FileSearch, Upload } from 'lucide-react';

export const PdfEmptyState: React.FC = () => (
  <div className="flex-1 flex flex-col items-center justify-center text-center min-h-[400px] opacity-0 animate-[fadeIn_0.5s_ease-out_forwards] p-6">
    <div className="relative mb-8 group">
      <div className="absolute inset-0 bg-indigo-500/20 blur-xl rounded-full group-hover:bg-indigo-500/30 transition-all duration-500"></div>
      <div className="relative w-24 h-24 bg-slate-800/80 backdrop-blur-sm border border-slate-700 rounded-2xl flex items-center justify-center shadow-2xl rotate-3 group-hover:rotate-6 transition-transform duration-300">
        <FileSearch className="text-indigo-400" size={40} strokeWidth={1.5} />
      </div>
      <div className="absolute -right-4 -bottom-4 w-16 h-16 bg-slate-800/90 backdrop-blur-md border border-slate-600 rounded-xl flex items-center justify-center shadow-xl -rotate-6 group-hover:-rotate-3 transition-transform duration-300">
        <Upload className="text-emerald-400" size={24} strokeWidth={2} />
      </div>
    </div>

    <h2 className="text-2xl md:text-3xl font-bold text-white mb-3">
      智能 PDF 提取
    </h2>
    <p className="text-slate-400 max-w-md mx-auto text-base md:text-lg leading-relaxed">
      上传 PDF 文档，AI 将自动提取结构化数据。
      在下方选择模板开始使用。
    </p>
  </div>
);
