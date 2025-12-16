
import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { Copy, Check } from 'lucide-react';

interface MarkdownRendererProps {
  content: string;
  isStreaming?: boolean;
}

const CodeBlock = ({ language, children, ...props }: any) => {
  const [isCopied, setIsCopied] = useState(false);

  const handleCopy = async () => {
    if (!children) return;
    try {
        await navigator.clipboard.writeText(String(children));
        setIsCopied(true);
        setTimeout(() => setIsCopied(false), 2000);
    } catch (err) {
        console.error("Failed to copy code", err);
    }
  };

  return (
    <div className="rounded-lg overflow-hidden my-3 border border-slate-700/50 shadow-sm group font-sans bg-[#0f172a]">
      <div className="bg-slate-900/80 px-3 py-2 text-xs text-slate-400 border-b border-slate-700/50 flex justify-between items-center backdrop-blur-sm">
        <span className="font-mono text-slate-500 font-bold lowercase">{language || 'text'}</span>
        <button 
          onClick={handleCopy} 
          className="flex items-center gap-1.5 text-slate-500 hover:text-white transition-colors p-1.5 rounded-md hover:bg-white/5"
          title="Copy to clipboard"
        >
          {isCopied ? <Check size={14} className="text-emerald-400" /> : <Copy size={14} />}
          <span className="text-[10px] font-medium">{isCopied ? 'Copied' : 'Copy'}</span>
        </button>
      </div>
      <SyntaxHighlighter
        style={vscDarkPlus}
        language={language}
        PreTag="div"
        customStyle={{ margin: 0, padding: '1rem', background: 'transparent', fontSize: '0.875rem', lineHeight: '1.6' }}
        wrapLines={true}
        wrapLongLines={true}
        {...props}
      >
        {String(children).replace(/\n$/, '')}
      </SyntaxHighlighter>
    </div>
  );
};

const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content, isStreaming }) => {
  return (
    <div className="prose prose-invert prose-sm sm:prose-base max-w-none break-words">
      <ReactMarkdown
        components={{
          code({ node, inline, className, children, ...props }: any) {
            const match = /language-(\w+)/.exec(className || '');
            return !inline && match ? (
              <CodeBlock language={match[1]} children={children} {...props} />
            ) : (
              <code className={`${className} bg-slate-800 text-orange-300 px-1 py-0.5 rounded text-sm`} {...props}>
                {children}
              </code>
            );
          },
          a: ({ node, ...props }) => (
            <a target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:underline" {...props} />
          ),
          ul: ({ node, ...props }) => <ul className="list-disc pl-5 my-2 space-y-1" {...props} />,
          ol: ({ node, ...props }) => <ol className="list-decimal pl-5 my-2 space-y-1" {...props} />,
          blockquote: ({ node, ...props }) => (
            <blockquote className="border-l-4 border-slate-600 pl-4 italic text-slate-400 my-2" {...props} />
          ),
        }}
      >
        {content}
      </ReactMarkdown>
      {/* Blinking Cursor */}
      {isStreaming && (
          <span className="inline-block w-1.5 h-4 ml-1 bg-indigo-400 animate-pulse align-sub duration-75" />
      )}
    </div>
  );
};

export default MarkdownRenderer;
