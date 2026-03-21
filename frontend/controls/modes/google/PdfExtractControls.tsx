import React, { useState } from 'react';
import { Sliders } from 'lucide-react';
import { PdfExtractControlsProps } from '../../types';

export const PdfExtractControls: React.FC<PdfExtractControlsProps> = ({
  selectedTemplate,
  setSelectedTemplate,
  templates = [],
  showAdvanced,
  setShowAdvanced
}) => {
  const [showTemplateMenu, setShowTemplateMenu] = useState(false);

  const currentTemplate = templates.find(t => t.id === selectedTemplate);
  const templateLabel = currentTemplate?.name || 'Invoice';
  const templateIcon = currentTemplate?.icon || '📄';

  return (
    <>
      <div className="relative">
        <button
          onClick={() => setShowTemplateMenu(!showTemplateMenu)}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-800/50 text-slate-300 hover:bg-slate-800 border border-transparent hover:border-slate-600 transition-all"
        >
          <span className="text-sm">{templateIcon}</span>
          {templateLabel}
        </button>
        {showTemplateMenu && (
          <>
            <div className="fixed inset-0 z-10" onClick={() => setShowTemplateMenu(false)} />
            <div className="absolute bottom-full right-0 mb-2 w-56 bg-slate-900 border border-slate-700 rounded-xl shadow-xl z-20 overflow-hidden animate-[fadeIn_0.1s_ease-out]">
              <div className="p-1 max-h-64 overflow-y-auto custom-scrollbar">
                {templates.map((template) => (
                  <button
                    key={template.id}
                    onClick={() => { setSelectedTemplate(template.id); setShowTemplateMenu(false); }}
                    className={`w-full text-left px-3 py-2 rounded-lg text-xs flex items-center gap-2 ${selectedTemplate === template.id ? 'bg-indigo-600 text-white' : 'text-slate-300 hover:bg-slate-800'}`}
                  >
                    <span className="text-base">{template.icon}</span>
                    <div className="flex-1 min-w-0">
                      <div className="font-medium">{template.name}</div>
                      <div className="text-[10px] text-slate-400 truncate">{template.description}</div>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </>
        )}
      </div>

      <button
        onClick={() => setShowAdvanced(!showAdvanced)}
        className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border border-transparent transition-all ${showAdvanced ? 'bg-slate-800 text-white' : 'bg-slate-800/50 text-slate-400 hover:text-slate-200'}`}
        title="高级设置：额外提取指令"
      >
        <Sliders size={14} />
      </button>
    </>
  );
};

export default PdfExtractControls;
