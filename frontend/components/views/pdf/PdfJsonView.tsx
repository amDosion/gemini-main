import React from 'react';

interface PdfJsonViewProps {
  data: Record<string, any>;
}

export const PdfJsonView: React.FC<PdfJsonViewProps> = ({ data }) => {
  return (
    <pre className="bg-slate-900/50 border border-slate-700/50 rounded-lg p-4 text-sm text-slate-300 overflow-x-auto font-mono">
      {JSON.stringify(data, null, 2)}
    </pre>
  );
};
