/**
 * Module type declarations for `react-syntax-highlighter` and its submodules.
 *
 * Rationale: the package ships without bundled types and there is no
 * `@types/react-syntax-highlighter` declared in package.json. Without these
 * declarations, strict TypeScript flags all imports as implicit `any` (TS7016).
 *
 * These minimal declarations preserve type safety for our usage (component
 * props + language/style imports) without pulling a full typed mirror.
 */

declare module 'react-syntax-highlighter' {
  import type { ComponentType, CSSProperties, ReactNode } from 'react';

  /**
   * Named props for react-syntax-highlighter — 严格类型，typo 会触发错误。
   * 修 type-design-analyzer NEEDS-IMPROVEMENT：原 `SyntaxHighlighterProps` 含
   * `[key: string]: unknown` index signature 让任意 prop 通过，与命名 props
   * 分离后 typo 现在能被编译器捕获。
   */
  export interface SyntaxHighlighterNamedProps {
    language?: string;
    style?: { [key: string]: CSSProperties };
    customStyle?: CSSProperties;
    codeTagProps?: { style?: CSSProperties; className?: string };
    useInlineStyles?: boolean;
    showLineNumbers?: boolean;
    showInlineLineNumbers?: boolean;
    startingLineNumber?: number;
    lineNumberStyle?: CSSProperties | ((lineNumber: number) => CSSProperties);
    wrapLines?: boolean;
    wrapLongLines?: boolean;
    lineProps?: { style?: CSSProperties; className?: string };
    renderer?: unknown;
    PreTag?: ComponentType<Record<string, unknown>> | keyof JSX.IntrinsicElements;
    CodeTag?: ComponentType<Record<string, unknown>> | keyof JSX.IntrinsicElements;
    className?: string;
    children?: ReactNode;
  }

  /**
   * Passthrough props 显式 opt-in：调用方需要透传未知 prop（如 data-* / aria-*
   * 或第三方扩展）时，使用 intersection `SyntaxHighlighterNamedProps & PassthroughProps`。
   */
  export interface SyntaxHighlighterPassthroughProps {
    [key: string]: unknown;
  }

  /** Default export type：命名 props（严格）；调用方可显式 intersect Passthrough。 */
  export type SyntaxHighlighterProps = SyntaxHighlighterNamedProps;

  type Highlighter = ComponentType<SyntaxHighlighterProps> & {
    registerLanguage: (name: string, language: unknown) => void;
  };
  export const Prism: Highlighter;
  export const Light: Highlighter;
  export const PrismLight: Highlighter;
  export const PrismAsyncLight: Highlighter;
  export const LightAsync: Highlighter;
  const SyntaxHighlighter: ComponentType<SyntaxHighlighterProps>;
  export default SyntaxHighlighter;
}

declare module 'react-syntax-highlighter/dist/esm/styles/prism' {
  import type { CSSProperties } from 'react';
  type StyleMap = { [key: string]: CSSProperties };
  export const oneDark: StyleMap;
  export const oneLight: StyleMap;
  export const vscDarkPlus: StyleMap;
  export const atomDark: StyleMap;
  export const tomorrow: StyleMap;
  export const dracula: StyleMap;
  export const okaidia: StyleMap;
  export const prism: StyleMap;
  const styles: StyleMap;
  export default styles;
}

declare module 'react-syntax-highlighter/dist/esm/languages/prism/*' {
  const language: unknown;
  export default language;
}

declare module 'react-syntax-highlighter/dist/cjs/languages/prism/*' {
  const language: unknown;
  export default language;
}

declare module 'react-syntax-highlighter/dist/esm/styles/hljs' {
  import type { CSSProperties } from 'react';
  type StyleMap = { [key: string]: CSSProperties };
  const styles: StyleMap;
  export default styles;
  export const atomOneDark: StyleMap;
  export const atomOneLight: StyleMap;
  export const githubGist: StyleMap;
}

declare module 'react-syntax-highlighter/dist/esm/languages/hljs/*' {
  const language: unknown;
  export default language;
}
