import React from 'react';
import ReactMarkdown from 'react-markdown';

interface PdfMarkdownViewProps {
  data: Record<string, any>;
}

export const PdfMarkdownView: React.FC<PdfMarkdownViewProps> = ({ data }) => {
  // 将数据转换为 Markdown 格式
  const generateMarkdown = (obj: Record<string, any>, level: number = 1): string => {
    let md = '';
    const headingPrefix = '#'.repeat(Math.min(level, 6));

    for (const [key, value] of Object.entries(obj)) {
      if (Array.isArray(value)) {
        md += `${headingPrefix} ${key}\n\n`;
        if (value.length === 0) {
          md += '*无数据*\n\n';
        } else if (typeof value[0] === 'object' && value[0] !== null) {
          // 数组对象转表格
          const headers = Object.keys(value[0]);
          md += '| # | ' + headers.join(' | ') + ' |\n';
          md += '| --- | ' + headers.map(() => '---').join(' | ') + ' |\n';
          value.forEach((item, idx) => {
            const cells = headers.map(h => String((item as Record<string, any>)[h] ?? '-'));
            md += `| ${idx + 1} | ${cells.join(' | ')} |\n`;
          });
          md += '\n';
        } else {
          // 简单数组
          value.forEach((item, idx) => {
            md += `${idx + 1}. ${String(item)}\n`;
          });
          md += '\n';
        }
      } else if (typeof value === 'object' && value !== null) {
        md += `${headingPrefix} ${key}\n\n`;
        md += generateMarkdown(value, level + 1);
      } else {
        md += `**${key}**: ${value ?? '-'}\n\n`;
      }
    }
    return md;
  };

  // 如果数据本身包含 markdown 字段，直接使用
  const markdownContent = data.markdown && typeof data.markdown === 'string' 
    ? data.markdown 
    : generateMarkdown(data);

  return (
    <div className="text-slate-300 leading-relaxed markdown-body prose prose-invert max-w-none">
      <ReactMarkdown
        components={{
          h1: ({ node, ...props }) => <h1 className="text-2xl font-bold mb-4 text-white border-b border-slate-700 pb-2" {...props} />,
          h2: ({ node, ...props }) => <h2 className="text-xl font-bold mb-3 text-white mt-6" {...props} />,
          h3: ({ node, ...props }) => <h3 className="text-lg font-semibold mb-2 text-white mt-4" {...props} />,
          p: ({ node, ...props }) => <p className="mb-4 last:mb-0" {...props} />,
          ul: ({ node, ...props }) => <ul className="list-disc pl-5 mb-4 space-y-1" {...props} />,
          ol: ({ node, ...props }) => <ol className="list-decimal pl-5 mb-4 space-y-1" {...props} />,
          li: ({ node, ...props }) => <li className="pl-1" {...props} />,
          strong: ({ node, ...props }) => <strong className="font-semibold text-indigo-300" {...props} />,
          code: ({ node, ...props }) => <code className="bg-slate-800 px-1.5 py-0.5 rounded text-sm font-mono text-indigo-300" {...props} />,
          pre: ({ node, ...props }) => <pre className="bg-slate-900/50 p-4 rounded-lg overflow-x-auto my-4 text-sm font-mono border border-slate-800" {...props} />,
          blockquote: ({ node, ...props }) => <blockquote className="border-l-4 border-indigo-500 pl-4 py-1 my-4 text-slate-400 italic bg-slate-800/30 rounded-r" {...props} />,
          a: ({ node, ...props }) => <a className="text-indigo-400 hover:text-indigo-300 underline" target="_blank" rel="noopener noreferrer" {...props} />,
          table: ({ node, ...props }) => <table className="w-full border-collapse my-4" {...props} />,
          thead: ({ node, ...props }) => <thead className="bg-slate-800" {...props} />,
          th: ({ node, ...props }) => <th className="px-3 py-2 text-left text-xs font-semibold text-slate-300 border border-slate-700" {...props} />,
          td: ({ node, ...props }) => <td className="px-3 py-2 text-sm text-slate-200 border border-slate-700/50" {...props} />,
          tr: ({ node, ...props }) => <tr className="hover:bg-slate-800/30" {...props} />,
        }}
      >
        {markdownContent}
      </ReactMarkdown>
    </div>
  );
};
