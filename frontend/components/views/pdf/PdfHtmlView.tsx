import React from 'react';
import { Download } from 'lucide-react';

interface PdfHtmlViewProps {
  data: Record<string, any>;
}

export const PdfHtmlView: React.FC<PdfHtmlViewProps> = ({ data }) => {
  const escapeHtml = (str: string): string => {
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  };

  // 渲染单个值
  const renderValue = (value: any): React.ReactNode => {
    if (value === null || value === undefined) return <span className="text-slate-500">-</span>;
    if (typeof value === 'boolean') return <span className={value ? 'text-green-400' : 'text-red-400'}>{value ? '是' : '否'}</span>;
    return <span className="text-slate-100">{String(value)}</span>;
  };

  // 渲染数组为表格
  const renderArrayTable = (items: any[], title: string) => {
    if (items.length === 0) return <p className="text-slate-500 italic text-sm">无数据</p>;
    
    const firstItem = items[0];
    if (typeof firstItem === 'object' && firstItem !== null) {
      const headers = Object.keys(firstItem);
      return (
        <div className="overflow-x-auto mt-2">
          <table className="w-full border-collapse text-sm">
            <thead>
              <tr className="bg-slate-800/80">
                <th className="px-3 py-2 text-left text-xs font-medium text-slate-400 border border-slate-700">#</th>
                {headers.map(h => (
                  <th key={h} className="px-3 py-2 text-left text-xs font-medium text-slate-400 border border-slate-700">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.map((item, idx) => (
                <tr key={idx} className="hover:bg-slate-800/30">
                  <td className="px-3 py-2 text-slate-500 border border-slate-700/50">{idx + 1}</td>
                  {headers.map(h => (
                    <td key={h} className="px-3 py-2 text-slate-200 border border-slate-700/50">
                      {renderValue((item as Record<string, any>)[h])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }
    
    // 简单数组
    return (
      <ol className="list-decimal list-inside space-y-1 mt-2 text-slate-200">
        {items.map((item, idx) => (
          <li key={idx}>{renderValue(item)}</li>
        ))}
      </ol>
    );
  };

  // 渲染标题
  const renderHeading = (text: string, level: number): React.ReactNode => {
    const classes = [
      'text-xl font-bold text-indigo-400 mt-6 mb-3',
      'text-lg font-semibold text-indigo-300 mt-4 mb-2',
      'text-base font-medium text-indigo-200 mt-3 mb-2',
    ][Math.min(level - 1, 2)];

    switch (Math.min(level + 1, 6)) {
      case 2: return <h2 className={classes}>{text}</h2>;
      case 3: return <h3 className={classes}>{text}</h3>;
      case 4: return <h4 className={classes}>{text}</h4>;
      case 5: return <h5 className={classes}>{text}</h5>;
      case 6: return <h6 className={classes}>{text}</h6>;
      default: return <h2 className={classes}>{text}</h2>;
    }
  };

  // 递归渲染对象
  const renderObject = (obj: Record<string, any>, level: number = 1): React.ReactNode => {
    return (
      <div className={level > 1 ? 'ml-4 pl-4 border-l-2 border-slate-700' : ''}>
        {Object.entries(obj).map(([key, value]) => {
          if (Array.isArray(value)) {
            return (
              <div key={key} className="mb-4">
                {renderHeading(key, level)}
                {renderArrayTable(value, key)}
              </div>
            );
          }
          
          if (typeof value === 'object' && value !== null) {
            return (
              <div key={key} className="mb-4">
                {renderHeading(key, level)}
                {renderObject(value, level + 1)}
              </div>
            );
          }
          
          return (
            <div key={key} className="flex items-start gap-3 py-2 px-3 rounded-lg bg-slate-800/30 mb-2">
              <span className="text-slate-400 font-medium min-w-[120px] shrink-0">{key}:</span>
              {renderValue(value)}
            </div>
          );
        })}
      </div>
    );
  };

  // 生成可下载的 HTML 文档
  const generateDownloadHtml = (): string => {
    const generateHtmlContent = (obj: Record<string, any>, level: number = 1): string => {
      let html = '';
      const HeadingTag = `h${Math.min(level, 6)}`;

      for (const [key, value] of Object.entries(obj)) {
        if (Array.isArray(value)) {
          html += `<${HeadingTag} class="section-title">${escapeHtml(key)}</${HeadingTag}>`;
          if (value.length === 0) {
            html += '<p class="empty">无数据</p>';
          } else if (typeof value[0] === 'object' && value[0] !== null) {
            const headers = Object.keys(value[0]);
            html += '<table><thead><tr><th>#</th>';
            headers.forEach(h => { html += `<th>${escapeHtml(h)}</th>`; });
            html += '</tr></thead><tbody>';
            value.forEach((item, idx) => {
              html += `<tr><td>${idx + 1}</td>`;
              headers.forEach(h => {
                html += `<td>${escapeHtml(String((item as Record<string, any>)[h] ?? '-'))}</td>`;
              });
              html += '</tr>';
            });
            html += '</tbody></table>';
          } else {
            html += '<ol>';
            value.forEach(item => { html += `<li>${escapeHtml(String(item))}</li>`; });
            html += '</ol>';
          }
        } else if (typeof value === 'object' && value !== null) {
          html += `<${HeadingTag} class="section-title">${escapeHtml(key)}</${HeadingTag}>`;
          html += `<div class="nested">${generateHtmlContent(value, level + 1)}</div>`;
        } else {
          html += `<div class="field"><span class="label">${escapeHtml(key)}:</span> <span class="value">${escapeHtml(String(value ?? '-'))}</span></div>`;
        }
      }
      return html;
    };

    return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PDF 提取结果</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f8fafc; color: #1e293b; padding: 2rem; line-height: 1.6; max-width: 900px; margin: 0 auto; }
    h1, h2, h3, h4, h5, h6 { color: #0f172a; margin: 1.5rem 0 0.75rem; }
    h1 { font-size: 1.75rem; border-bottom: 2px solid #e2e8f0; padding-bottom: 0.5rem; }
    .section-title { color: #4f46e5; }
    .field { margin: 0.5rem 0; padding: 0.75rem; background: #fff; border: 1px solid #e2e8f0; border-radius: 0.5rem; }
    .label { color: #64748b; font-weight: 500; }
    .value { color: #0f172a; }
    .nested { margin-left: 1rem; padding-left: 1rem; border-left: 2px solid #e2e8f0; }
    .empty { color: #94a3b8; font-style: italic; }
    table { width: 100%; border-collapse: collapse; margin: 1rem 0; background: #fff; }
    th, td { padding: 0.75rem; text-align: left; border: 1px solid #e2e8f0; }
    th { background: #f1f5f9; color: #475569; font-size: 0.75rem; text-transform: uppercase; font-weight: 600; }
    tr:hover td { background: #f8fafc; }
    ol, ul { margin: 0.5rem 0; padding-left: 1.5rem; }
    li { margin: 0.25rem 0; }
  </style>
</head>
<body>
  <h1>📄 PDF 提取结果</h1>
  ${generateHtmlContent(data)}
</body>
</html>`;
  };

  const handleDownload = () => {
    const htmlDoc = generateDownloadHtml();
    const blob = new Blob([htmlDoc], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `pdf-extract-${Date.now()}.html`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-4">
      {/* 下载按钮 */}
      <div className="flex justify-end">
        <button
          onClick={handleDownload}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-700/50 hover:bg-slate-700 border border-slate-600 rounded-lg text-xs text-slate-200 transition-all"
        >
          <Download size={14} />
          下载 HTML
        </button>
      </div>

      {/* 渲染后的网页内容 */}
      <div className="bg-slate-900/30 border border-slate-700/50 rounded-lg p-6">
        <h1 className="text-2xl font-bold text-white mb-6 pb-3 border-b border-slate-700">
          📄 PDF 提取结果
        </h1>
        {renderObject(data)}
      </div>
    </div>
  );
};
