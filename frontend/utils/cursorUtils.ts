/**
 * 将光标 HTML 注入到文本内容的末尾
 * @param content - Markdown 文本内容
 * @param showCursor - 是否显示光标
 * @returns 注入光标后的 Markdown 文本
 */
export function injectCursorToContent(
  content: string,
  showCursor: boolean
): string {
  if (!showCursor || !content) {
    return content;
  }

  // 光标的 HTML 标记(使用 inline 元素确保紧跟文字)
  const cursorHTML = '<span class="inline-block w-0.5 h-4 ml-0.5 bg-indigo-400 animate-pulse" style="animation-duration: 1s; vertical-align: text-bottom;"></span>';

  // 在内容末尾添加光标
  const trimmedContent = content.trimEnd();
  const trailingWhitespace = content.slice(trimmedContent.length);

  return trimmedContent + cursorHTML + trailingWhitespace;
}
