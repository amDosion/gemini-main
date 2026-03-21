
import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import rehypeRaw from 'rehype-raw';
import { PrismLight as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import bash from 'react-syntax-highlighter/dist/esm/languages/prism/bash';
import css from 'react-syntax-highlighter/dist/esm/languages/prism/css';
import javascript from 'react-syntax-highlighter/dist/esm/languages/prism/javascript';
import json from 'react-syntax-highlighter/dist/esm/languages/prism/json';
import jsx from 'react-syntax-highlighter/dist/esm/languages/prism/jsx';
import markdown from 'react-syntax-highlighter/dist/esm/languages/prism/markdown';
import markup from 'react-syntax-highlighter/dist/esm/languages/prism/markup';
import python from 'react-syntax-highlighter/dist/esm/languages/prism/python';
import sql from 'react-syntax-highlighter/dist/esm/languages/prism/sql';
import tsx from 'react-syntax-highlighter/dist/esm/languages/prism/tsx';
import typescript from 'react-syntax-highlighter/dist/esm/languages/prism/typescript';
import yaml from 'react-syntax-highlighter/dist/esm/languages/prism/yaml';
import { Copy, Check, ChevronDown, ChevronRight, Brain } from 'lucide-react';

SyntaxHighlighter.registerLanguage('bash', bash);
SyntaxHighlighter.registerLanguage('sh', bash);
SyntaxHighlighter.registerLanguage('shell', bash);
SyntaxHighlighter.registerLanguage('css', css);
SyntaxHighlighter.registerLanguage('javascript', javascript);
SyntaxHighlighter.registerLanguage('js', javascript);
SyntaxHighlighter.registerLanguage('json', json);
SyntaxHighlighter.registerLanguage('jsx', jsx);
SyntaxHighlighter.registerLanguage('markdown', markdown);
SyntaxHighlighter.registerLanguage('md', markdown);
SyntaxHighlighter.registerLanguage('html', markup);
SyntaxHighlighter.registerLanguage('xml', markup);
SyntaxHighlighter.registerLanguage('markup', markup);
SyntaxHighlighter.registerLanguage('python', python);
SyntaxHighlighter.registerLanguage('py', python);
SyntaxHighlighter.registerLanguage('sql', sql);
SyntaxHighlighter.registerLanguage('tsx', tsx);
SyntaxHighlighter.registerLanguage('typescript', typescript);
SyntaxHighlighter.registerLanguage('ts', typescript);
SyntaxHighlighter.registerLanguage('yaml', yaml);
SyntaxHighlighter.registerLanguage('yml', yaml);

// 思考块组件 - 用于渲染 AI 模型的 <think> 标签内容
const ThinkBlock: React.FC<{ children?: React.ReactNode }> = ({ children }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  
  return (
    <div className="my-3 rounded-lg border border-slate-700/50 bg-slate-900/50 overflow-hidden">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center gap-2 px-3 py-2 text-sm text-slate-400 hover:text-slate-300 hover:bg-slate-800/50 transition-colors"
      >
        {isExpanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <Brain size={14} className="text-purple-400" />
        <span className="font-medium">思考过程</span>
      </button>
      {isExpanded && (
        <div className="px-4 py-3 text-sm text-slate-400 border-t border-slate-700/50 bg-slate-900/30">
          {children}
        </div>
      )}
    </div>
  );
};

interface MarkdownRendererProps {
  content: string;
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

const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content }) => {
  // 自定义组件映射，包含标准 HTML 元素和自定义标签（如 AI 模型的 <think>）
  const customComponents: any = {
    // 处理 AI 模型的 <think> 标签（DeepSeek、Claude 等模型的思考过程）
    think: ({ children }: { children?: React.ReactNode }) => <ThinkBlock>{children}</ThinkBlock>,
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
    a: ({ node, ...props }: any) => (
      <a target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:underline" {...props} />
    ),
    ul: ({ node, ...props }: any) => <ul className="list-disc pl-5 my-2 space-y-1" {...props} />,
    ol: ({ node, ...props }: any) => <ol className="list-decimal pl-5 my-2 space-y-1" {...props} />,
    blockquote: ({ node, ...props }: any) => (
      <blockquote className="border-l-4 border-slate-600 pl-4 italic text-slate-400 my-2" {...props} />
    ),
  };

  return (
    <div className="prose prose-invert prose-sm sm:prose-base max-w-none break-words">
      <ReactMarkdown
        rehypePlugins={[rehypeRaw]}
        components={customComponents}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
};

export default MarkdownRenderer;
