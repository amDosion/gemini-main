import { safeCopyToClipboard } from '../../utils/safeOps';
import React, { useMemo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import type { Components, ExtraProps } from 'react-markdown';
import rehypeRaw from 'rehype-raw';
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize';
import type { PluggableList } from 'unified';
import { Copy, Check, ChevronDown, ChevronRight, Brain } from 'lucide-react';
import { STREAMING_CURSOR_CLASSNAME } from '../../utils/cursorUtils';

const MarkdownCodeHighlighter = React.lazy(() => import('./MarkdownCodeHighlighter'));

// 思考块组件 - 用于渲染 AI 模型的 <think> 标签内容
const ThinkBlock: React.FC<{ children?: React.ReactNode }> = ({ children }) => {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="my-3 rounded-lg border border-slate-700/50 bg-slate-900/50 overflow-hidden">
      <button
        aria-expanded={isExpanded}
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
  /**
   * 是否在渲染结果末尾追加流式光标。光标在 React 组件树内渲染,
   * 不经过 Markdown sanitizer,因此可使用纯 Tailwind 动画类。
   */
  showCursor?: boolean;
}

const CodeBlock = ({
  language,
  children,
  ...props
}: {
  language?: string;
  children?: React.ReactNode;
  [key: string]: unknown;
}) => {
  const [isCopied, setIsCopied] = useState(false);

  const handleCopy = async () => {
    if (!children) return;
    const ok = await safeCopyToClipboard(String(children));
    if (ok) {
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
    }
  };

  const codeText = String(children).replace(/\n$/, '');

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
      <React.Suspense
        fallback={
          <pre className="m-0 overflow-x-auto bg-transparent p-4 text-sm leading-relaxed text-slate-200">
            <code>{codeText}</code>
          </pre>
        }
      >
        <MarkdownCodeHighlighter language={language} syntaxProps={props}>
          {children}
        </MarkdownCodeHighlighter>
      </React.Suspense>
    </div>
  );
};

// Sanitize schema: allow common HTML but block script execution
const sanitizeSchema = {
  ...defaultSchema,
  tagNames: [...(defaultSchema.tagNames || []), 'think', 'details', 'summary', 'mark'],
  attributes: {
    ...defaultSchema.attributes,
    // W02R-019: do NOT allow inline `style` on chat/model-controlled markdown
    // (CSS injection / UI redress, e.g. position:fixed overlays). className only.
    '*': [...(defaultSchema.attributes?.['*'] || []), 'className'],
    img: [...(defaultSchema.attributes?.['img'] || []), 'src', 'alt', 'width', 'height', 'loading'],
    a: [...(defaultSchema.attributes?.['a'] || []), 'target', 'rel'],
  },
};
const markdownRehypePlugins: PluggableList = [rehypeRaw, [rehypeSanitize, sanitizeSchema]];

const toSafeMarkdownHref = (url: string): string => {
  try {
    const parsed = new URL(url);
    if (parsed.protocol === 'http:' || parsed.protocol === 'https:') {
      return parsed.toString();
    }
  } catch {
    // Relative or malformed model-supplied links should not become navigable.
  }
  return '';
};

const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content, showCursor = false }) => {
  // 自定义组件映射，包含标准 HTML 元素和自定义标签（如 AI 模型的 <think>）
  const customComponents = useMemo<
    Components & {
      think?: (props: { children?: React.ReactNode }) => React.ReactElement;
    }
  >(
    () => ({
      // 处理 AI 模型的 <think> 标签（DeepSeek、Claude 等模型的思考过程）
      think: ({ children }: { children?: React.ReactNode }) => <ThinkBlock>{children}</ThinkBlock>,
      code({
        node,
        inline,
        className,
        children,
        ...props
      }: React.ComponentPropsWithoutRef<'code'> & ExtraProps & { inline?: boolean }) {
        const match = /language-(\w+)/.exec(className || '');
        return !inline && match ? (
          <CodeBlock language={match[1]} children={children} {...props} />
        ) : (
          <code
            className={`${className} bg-slate-800 text-orange-300 px-1 py-0.5 rounded text-sm`}
            {...props}
          >
            {children}
          </code>
        );
      },
      a: ({ node, href, ...props }: React.ComponentPropsWithoutRef<'a'> & ExtraProps) => {
        const safeHref = typeof href === 'string' && href.trim() ? href : undefined;
        return (
          <a
            {...props}
            href={safeHref}
            target={safeHref ? '_blank' : undefined}
            rel={safeHref ? 'noopener noreferrer' : undefined}
            className="text-blue-400 hover:underline"
          />
        );
      },
      ul: ({ node, ...props }: React.ComponentPropsWithoutRef<'ul'> & ExtraProps) => (
        <ul className="list-disc pl-5 my-2 space-y-1" {...props} />
      ),
      ol: ({ node, ...props }: React.ComponentPropsWithoutRef<'ol'> & ExtraProps) => (
        <ol className="list-decimal pl-5 my-2 space-y-1" {...props} />
      ),
      blockquote: ({
        node,
        ...props
      }: React.ComponentPropsWithoutRef<'blockquote'> & ExtraProps) => (
        <blockquote
          className="border-l-4 border-slate-600 pl-4 italic text-slate-400 my-2"
          {...props}
        />
      ),
    }),
    []
  );

  return (
    <div className="prose prose-invert prose-sm sm:prose-base max-w-none break-words">
      <ReactMarkdown
        rehypePlugins={markdownRehypePlugins}
        components={customComponents}
        urlTransform={toSafeMarkdownHref}
      >
        {content}
      </ReactMarkdown>
      {showCursor && (
        <span
          className={STREAMING_CURSOR_CLASSNAME}
          aria-hidden="true"
          data-testid="streaming-cursor"
        />
      )}
    </div>
  );
};

export default MarkdownRenderer;
