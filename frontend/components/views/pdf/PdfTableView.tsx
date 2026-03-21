import React, { useState, useMemo } from 'react';
import { Copy, Check, ChevronDown, ChevronUp } from 'lucide-react';

interface PdfTableViewProps {
  data: Record<string, any>;
}

// 长文本阈值
const LONG_TEXT_THRESHOLD = 100;

export const PdfTableView: React.FC<PdfTableViewProps> = ({ data }) => {
  const [copiedCell, setCopiedCell] = useState<string | null>(null);
  const [expandedCells, setExpandedCells] = useState<Set<string>>(new Set());

  const copyToClipboard = (text: string, cellId: string) => {
    navigator.clipboard.writeText(text);
    setCopiedCell(cellId);
    setTimeout(() => setCopiedCell(null), 2000);
  };

  const toggleExpand = (cellId: string) => {
    setExpandedCells(prev => {
      const next = new Set(prev);
      next.has(cellId) ? next.delete(cellId) : next.add(cellId);
      return next;
    });
  };

  // 将数据转换为表格结构
  const tableData = useMemo(() => {
    // 分离简单字段和数组字段
    const simpleFields: Record<string, any> = {};
    const arrayFields: { key: string; items: any[] }[] = [];

    Object.entries(data).forEach(([key, value]) => {
      if (Array.isArray(value) && value.length > 0 && typeof value[0] === 'object') {
        arrayFields.push({ key, items: value });
      } else {
        simpleFields[key] = value;
      }
    });

    return { simpleFields, arrayFields };
  }, [data]);

  // 渲染单元格值
  const renderCellValue = (value: any, cellId: string): React.ReactNode => {
    if (value === null || value === undefined) {
      return <span className="text-slate-500">-</span>;
    }

    const strValue = typeof value === 'object' ? JSON.stringify(value) : String(value);
    const isLong = strValue.length > LONG_TEXT_THRESHOLD;
    const isExpanded = expandedCells.has(cellId);
    const isCopied = copiedCell === cellId;

    return (
      <div className="group relative">
        <div className={`text-slate-200 ${isLong && !isExpanded ? 'line-clamp-2' : ''}`}>
          {strValue}
        </div>
        <div className="flex items-center gap-1 mt-1">
          {isLong && (
            <button
              onClick={() => toggleExpand(cellId)}
              className="text-[10px] text-indigo-400 hover:text-indigo-300 flex items-center gap-0.5"
            >
              {isExpanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              {isExpanded ? '收起' : '展开'}
            </button>
          )}
          <button
            onClick={() => copyToClipboard(strValue, cellId)}
            className="opacity-0 group-hover:opacity-100 p-1 hover:bg-slate-700 rounded transition-all"
            title="复制"
          >
            {isCopied ? (
              <Check size={12} className="text-green-400" />
            ) : (
              <Copy size={12} className="text-slate-500" />
            )}
          </button>
        </div>
      </div>
    );
  };

  // 渲染数组表格（Excel 风格）
  const renderArrayTable = (items: any[], tableKey: string) => {
    if (items.length === 0) return <p className="text-slate-500 text-sm italic">无数据</p>;

    const columns = Object.keys(items[0]);

    return (
      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="bg-slate-800">
              <th className="px-3 py-2 text-left text-xs font-semibold text-slate-300 border border-slate-700 w-12">
                #
              </th>
              {columns.map(col => (
                <th
                  key={col}
                  className="px-3 py-2 text-left text-xs font-semibold text-slate-300 border border-slate-700 min-w-[120px]"
                >
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {items.map((item, rowIdx) => (
              <tr
                key={rowIdx}
                className={`${rowIdx % 2 === 0 ? 'bg-slate-900/30' : 'bg-slate-900/50'} hover:bg-slate-800/50`}
              >
                <td className="px-3 py-2 text-slate-500 border border-slate-700/50 text-center font-mono">
                  {rowIdx + 1}
                </td>
                {columns.map(col => (
                  <td key={col} className="px-3 py-2 border border-slate-700/50 max-w-[300px]">
                    {renderCellValue(item[col], `${tableKey}-${rowIdx}-${col}`)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  // 渲染简单字段表格（横向：字段名作为列头，值作为单行）
  const renderSimpleFieldsTable = () => {
    const entries = Object.entries(tableData.simpleFields);
    if (entries.length === 0) return null;

    return (
      <div className="overflow-x-auto mb-6">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="bg-slate-800">
              {entries.map(([key]) => (
                <th
                  key={key}
                  className="px-3 py-2 text-left text-xs font-semibold text-slate-300 border border-slate-700 min-w-[100px]"
                >
                  {key}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr className="bg-slate-900/30 hover:bg-slate-800/50">
              {entries.map(([key, value]) => (
                <td key={key} className="px-3 py-2 border border-slate-700/50 max-w-[250px]">
                  {renderCellValue(value, `simple-${key}`)}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* 简单字段表格 */}
      {Object.keys(tableData.simpleFields).length > 0 && (
        <div>
          <h3 className="text-sm font-medium text-slate-400 mb-2">基本信息</h3>
          {renderSimpleFieldsTable()}
        </div>
      )}

      {/* 数组字段表格 */}
      {tableData.arrayFields.map(({ key, items }) => (
        <div key={key}>
          <h3 className="text-sm font-medium text-slate-400 mb-2">
            {key}
            <span className="ml-2 text-xs text-slate-500">({items.length} 条记录)</span>
          </h3>
          {renderArrayTable(items, key)}
        </div>
      ))}

      {/* 如果没有数据 */}
      {Object.keys(tableData.simpleFields).length === 0 && tableData.arrayFields.length === 0 && (
        <div className="text-center py-10 text-slate-500">暂无数据</div>
      )}
    </div>
  );
};
