/**
 * 流式光标的 Tailwind 类名(纯 className,不含 inline style)。
 *
 * 安全约束(W02R-019):聊天 / 模型可控的 Markdown 经过 rehype-sanitize,
 * inline `style` 属性会被剥离。因此光标不能再以原始 HTML 字符串(含 style)
 * 的方式拼接进 Markdown 内容——那样既绕过了 sanitizer 边界,动画也会失效。
 *
 * 光标改由 `MarkdownRenderer` 在 React 组件树内部渲染(见其 `showCursor` prop),
 * 这里仅导出可复用的 class 字符串。动画完全由 Tailwind 类驱动,无需 inline style。
 */
export const STREAMING_CURSOR_CLASSNAME =
  'inline-block w-0.5 h-4 ml-0.5 align-text-bottom bg-indigo-400 animate-pulse';
